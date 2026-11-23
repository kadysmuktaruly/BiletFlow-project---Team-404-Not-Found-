"""Platform administration (SRS 4.12). Callers are Platform Admins (checked by the router's
dependency); every change here writes an audit entry (SRS 7 "Organizer and administrator
actions shall be auditable")."""

import csv
import io
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivationStatus,
    EventReportStatus,
    EventStatus,
    OrderStatus,
    PaymentStatus,
    SupportCaseStatus,
    UserRole,
)
from app.errors import AppError
from app.models import (
    Event,
    EventReport,
    Order,
    OrganizerProfile,
    PaidSalesActivation,
    Payment,
    PlatformSettings,
    PromoCode,
    PromotionalCampaign,
    Refund,
    SupportCase,
    User,
)
from app.schemas.admin import (
    AdminActivation,
    AdminActivationList,
    AdminEvent,
    AdminEventList,
    AdminOrder,
    AdminOrderList,
    AdminPayment,
    AdminPaymentList,
    AdminPromotion,
    AdminPromotionList,
    AdminReport,
    AdminReportList,
    AdminSummary,
    AdminUser,
    AdminUserList,
    ReportCreate,
    ReportReview,
    SettingsRead,
    SettingsUpdate,
)
from app.services import audit, platform_settings, promotions

LIMIT = 100
EXPORT_LIMIT = 10_000


def _pattern(q: str) -> str:
    escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _like(column: Any, q: str) -> Any:
    return column.ilike(_pattern(q), escape="\\")


async def _page[T](
    session: AsyncSession, query: Select[tuple[T]], limit: int
) -> tuple[list[T], bool]:
    rows = list(await session.scalars(query.limit(limit + 1)))
    return rows[:limit], len(rows) > limit


# --- overview -------------------------------------------------------------------------------


async def summary(session: AsyncSession) -> AdminSummary:
    async def count(query: Any) -> int:
        return int(await session.scalar(query) or 0)

    return AdminSummary(
        users=await count(select(func.count(User.id))),
        suspended_users=await count(select(func.count(User.id)).where(User.is_suspended)),
        events_published=await count(
            select(func.count(Event.id)).where(Event.status == EventStatus.PUBLISHED)
        ),
        suspended_events=await count(select(func.count(Event.id)).where(Event.is_suspended)),
        orders_confirmed=await count(
            select(func.count(Order.id)).where(Order.status == OrderStatus.CONFIRMED)
        ),
        payments_failed=await count(
            select(func.count(Payment.id)).where(Payment.status == PaymentStatus.FAILED)
        ),
        refunds=await count(select(func.count(Refund.id))),
        open_reports=await count(
            select(func.count(EventReport.id)).where(EventReport.status == EventReportStatus.OPEN)
        ),
        open_support_cases=await count(
            select(func.count(SupportCase.id)).where(
                SupportCase.status != SupportCaseStatus.RESOLVED
            )
        ),
        paid_sales_suspended=await count(
            select(func.count(PaidSalesActivation.id)).where(
                PaidSalesActivation.status == ActivationStatus.SUSPENDED
            )
        ),
    )


# --- users ----------------------------------------------------------------------------------


def _user(u: User) -> AdminUser:
    return AdminUser.model_validate(u, from_attributes=True)


def _users_query(
    q: str | None, role: UserRole | None, suspended: bool | None
) -> Select[tuple[User]]:
    query = select(User)
    if q and q.strip():
        query = query.where(or_(_like(User.email, q), _like(User.full_name, q)))
    if role is not None:
        query = query.where(User.role == role)
    if suspended is not None:
        query = query.where(User.is_suspended.is_(suspended))
    return query.order_by(User.created_at.desc())


async def list_users(
    session: AsyncSession, q: str | None, role: UserRole | None, suspended: bool | None
) -> AdminUserList:
    users, more = await _page(session, _users_query(q, role, suspended), LIMIT)
    return AdminUserList(items=[_user(u) for u in users], truncated=more)


async def set_user_suspended(
    session: AsyncSession, admin: User, user_id: uuid.UUID, suspended: bool, reason: str | None
) -> AdminUser:
    """A suspended user can't sign in, and their current tokens stop working at once
    (`app.deps.get_current_user` rejects them on every request)."""
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise AppError(404, "user_not_found", "User not found.")
    if user.role is UserRole.PLATFORM_ADMIN:
        raise AppError(409, "cannot_suspend_admin", "Platform Admins can't be suspended here.")
    if user.is_suspended != suspended:
        user.is_suspended = suspended
        user.suspended_at = datetime.now(UTC) if suspended else None
        audit.record(
            session,
            actor_id=admin.id,
            action="admin.user_suspended" if suspended else "admin.user_unsuspended",
            entity_type="user",
            entity_id=user.id,
            description=f"{'Suspended' if suspended else 'Reinstated'} {user.email}"
            + (f". Reason: {reason}" if reason else ""),
        )
        await session.commit()
    return _user(user)


# --- events and paid sales ----------------------------------------------------------------


def _events_query(
    q: str | None, status: EventStatus | None, suspended: bool | None
) -> Select[tuple[Event]]:
    query = select(Event).join(OrganizerProfile, OrganizerProfile.id == Event.organizer_profile_id)
    if q and q.strip():
        query = query.where(
            or_(
                _like(Event.title, q),
                _like(Event.slug, q),
                _like(OrganizerProfile.display_name, q),
                _like(OrganizerProfile.contact_email, q),
            )
        )
    if status is not None:
        query = query.where(Event.status == status)
    if suspended is not None:
        query = query.where(Event.is_suspended.is_(suspended))
    return query.order_by(Event.created_at.desc())


async def _admin_events(session: AsyncSession, events: Sequence[Event]) -> list[AdminEvent]:
    ids = [e.id for e in events]
    organizers = {
        p.id: p
        for p in await session.scalars(
            select(OrganizerProfile).where(
                OrganizerProfile.id.in_({e.organizer_profile_id for e in events})
            )
        )
    }
    activations = dict(
        (
            await session.execute(
                select(PaidSalesActivation.event_id, PaidSalesActivation.status).where(
                    PaidSalesActivation.event_id.in_(ids)
                )
            )
        )
        .tuples()
        .all()
    )
    reports = dict(
        (
            await session.execute(
                select(EventReport.event_id, func.count(EventReport.id))
                .where(EventReport.event_id.in_(ids), EventReport.status == EventReportStatus.OPEN)
                .group_by(EventReport.event_id)
            )
        )
        .tuples()
        .all()
    )
    return [
        AdminEvent(
            id=e.id,
            title=e.title,
            slug=e.slug,
            status=e.status,
            visibility=e.visibility,
            is_suspended=e.is_suspended,
            organizer_name=organizers[e.organizer_profile_id].display_name,
            organizer_email=organizers[e.organizer_profile_id].contact_email,
            starts_at=e.starts_at,
            paid_sales=activations.get(e.id),
            open_reports=reports.get(e.id, 0),
            created_at=e.created_at,
        )
        for e in events
    ]


async def list_events(
    session: AsyncSession, q: str | None, status: EventStatus | None, suspended: bool | None
) -> AdminEventList:
    events, more = await _page(session, _events_query(q, status, suspended), LIMIT)
    return AdminEventList(items=await _admin_events(session, events), truncated=more)


async def _event(session: AsyncSession, event_id: uuid.UUID) -> Event:
    event = await session.get(Event, event_id, with_for_update=True)
    if event is None:
        raise AppError(404, "event_not_found", "Event not found.")
    return event


async def set_event_suspended(
    session: AsyncSession, admin: User, event_id: uuid.UUID, suspended: bool, reason: str | None
) -> AdminEvent:
    """SRS 4.12 / SRS 11 "suspend a suspicious event and stop further sales". Checkout checks
    `Event.is_suspended` in the same transaction that reserves stock, so sales stop at once;
    the event also drops out of the public listing. Issued tickets stay valid."""
    event = await _event(session, event_id)
    if event.is_suspended != suspended:
        event.is_suspended = suspended
        audit.record(
            session,
            actor_id=admin.id,
            action="admin.event_suspended" if suspended else "admin.event_unsuspended",
            entity_type="event",
            entity_id=event.id,
            description=f"{'Suspended' if suspended else 'Reinstated'} “{event.title}”"
            + (f". Reason: {reason}" if reason else ""),
            event_id=event.id,
        )
        await session.commit()
    (read,) = await _admin_events(session, [event])
    return read


async def set_paid_sales_suspended(
    session: AsyncSession, admin: User, event_id: uuid.UUID, suspended: bool, reason: str | None
) -> AdminActivation:
    """SRS 4.5: suspend paid sales where fraud is suspected. Paid checkout and payment both
    check the activation status, so it takes effect for the next request. Free registration
    is unaffected."""
    from app.services.activation import refresh_status

    event = await _event(session, event_id)
    activation = await session.scalar(
        select(PaidSalesActivation)
        .where(PaidSalesActivation.event_id == event.id)
        .with_for_update()
    )
    if activation is None:
        raise AppError(404, "activation_not_found", "This event has no paid-sales record.")
    changed = (activation.status is ActivationStatus.SUSPENDED) != suspended
    if changed:
        if suspended:
            activation.status = ActivationStatus.SUSPENDED
            activation.suspended_at = datetime.now(UTC)
            activation.suspended_reason = reason
        else:
            activation.status = ActivationStatus.IN_PROGRESS
            activation.suspended_at = None
            activation.suspended_reason = None
            await refresh_status(session, activation, admin)
        audit.record(
            session,
            actor_id=admin.id,
            action="admin.paid_sales_suspended" if suspended else "admin.paid_sales_resumed",
            entity_type="paid_sales_activation",
            entity_id=activation.id,
            description=f"{'Suspended' if suspended else 'Resumed'} paid sales for "
            f"“{event.title}”" + (f". Reason: {reason}" if reason else ""),
            event_id=event.id,
        )
        await session.commit()
        # `updated_at` is set by the database on update; load it before reading it.
        await session.refresh(activation)
    (read,) = await _admin_activations(session, [activation])
    return read


async def _admin_activations(
    session: AsyncSession, activations: Sequence[PaidSalesActivation]
) -> list[AdminActivation]:
    rows = (
        await session.execute(
            select(Event.id, Event.title, OrganizerProfile.display_name)
            .join(OrganizerProfile, OrganizerProfile.id == Event.organizer_profile_id)
            .where(Event.id.in_({a.event_id for a in activations}))
        )
    ).tuples()
    events = {event_id: (title, organizer) for event_id, title, organizer in rows}
    return [
        AdminActivation(
            event_id=a.event_id,
            event_title=events[a.event_id][0],
            organizer_name=events[a.event_id][1],
            status=a.status,
            has_paid_ticket_type=a.has_paid_ticket_type,
            identity_verified=a.identity_verified,
            payout_account_connected=a.payout_account_connected,
            activation_fee_paid=a.activation_fee_paid,
            terms_accepted=a.terms_accepted,
            activation_fee_kzt=a.activation_fee_kzt,
            activated_at=a.activated_at,
            suspended_at=a.suspended_at,
            suspended_reason=a.suspended_reason,
            updated_at=a.updated_at,
        )
        for a in activations
    ]


async def list_activations(
    session: AsyncSession, q: str | None, status: ActivationStatus | None
) -> AdminActivationList:
    query = select(PaidSalesActivation).join(Event, Event.id == PaidSalesActivation.event_id)
    if q and q.strip():
        query = query.where(_like(Event.title, q))
    if status is not None:
        query = query.where(PaidSalesActivation.status == status)
    activations, more = await _page(
        session, query.order_by(PaidSalesActivation.updated_at.desc()), LIMIT
    )
    return AdminActivationList(items=await _admin_activations(session, activations), truncated=more)


# --- orders and payments ------------------------------------------------------------------


def _orders_query(q: str | None, status: OrderStatus | None) -> Select[tuple[Order]]:
    query = (
        select(Order).join(User, User.id == Order.user_id).join(Event, Event.id == Order.event_id)
    )
    if q and q.strip():
        query = query.where(
            or_(_like(Order.reference, q), _like(User.email, q), _like(Event.title, q))
        )
    if status is not None:
        query = query.where(Order.status == status)
    return query.order_by(Order.created_at.desc())


async def _admin_orders(session: AsyncSession, orders: Sequence[Order]) -> list[AdminOrder]:
    emails = dict(
        (
            await session.execute(
                select(User.id, User.email).where(User.id.in_({o.user_id for o in orders}))
            )
        )
        .tuples()
        .all()
    )
    titles = dict(
        (
            await session.execute(
                select(Event.id, Event.title).where(Event.id.in_({o.event_id for o in orders}))
            )
        )
        .tuples()
        .all()
    )
    return [
        AdminOrder(
            id=o.id,
            reference=o.reference,
            status=o.status,
            event_id=o.event_id,
            event_title=titles[o.event_id],
            buyer_email=emails[o.user_id],
            total_kzt=o.total_kzt,
            refunded_kzt=o.refunded_kzt,
            created_at=o.created_at,
        )
        for o in orders
    ]


async def list_orders(
    session: AsyncSession, q: str | None, status: OrderStatus | None
) -> AdminOrderList:
    orders, more = await _page(session, _orders_query(q, status), LIMIT)
    return AdminOrderList(items=await _admin_orders(session, orders), truncated=more)


def _payments_query(q: str | None, status: PaymentStatus | None) -> Select[tuple[Payment]]:
    query = (
        select(Payment)
        .join(User, User.id == Payment.user_id)
        .outerjoin(Order, Order.id == Payment.order_id)
        .outerjoin(Event, Event.id == Payment.event_id)
    )
    if q and q.strip():
        query = query.where(
            or_(
                _like(User.email, q),
                _like(Order.reference, q),
                _like(Payment.provider_reference, q),
                _like(Event.title, q),
            )
        )
    if status is not None:
        query = query.where(Payment.status == status)
    return query.order_by(Payment.created_at.desc())


async def _admin_payments(session: AsyncSession, payments: Sequence[Payment]) -> list[AdminPayment]:
    emails = dict(
        (
            await session.execute(
                select(User.id, User.email).where(User.id.in_({p.user_id for p in payments}))
            )
        )
        .tuples()
        .all()
    )
    references = dict(
        (
            await session.execute(
                select(Order.id, Order.reference).where(
                    Order.id.in_({p.order_id for p in payments if p.order_id})
                )
            )
        )
        .tuples()
        .all()
    )
    event_ids = {p.event_id for p in payments if p.event_id}
    event_ids |= set(
        await session.scalars(
            select(Order.event_id).where(Order.id.in_({p.order_id for p in payments if p.order_id}))
        )
    )
    titles = dict(
        (await session.execute(select(Event.id, Event.title).where(Event.id.in_(event_ids))))
        .tuples()
        .all()
    )
    order_events = dict(
        (
            await session.execute(
                select(Order.id, Order.event_id).where(
                    Order.id.in_({p.order_id for p in payments if p.order_id})
                )
            )
        )
        .tuples()
        .all()
    )
    out = []
    for p in payments:
        event_id = p.event_id or (order_events.get(p.order_id) if p.order_id else None)
        out.append(
            AdminPayment(
                id=p.id,
                purpose=p.purpose,
                status=p.status,
                amount_kzt=p.amount_kzt,
                user_email=emails[p.user_id],
                event_title=titles.get(event_id) if event_id else None,
                order_reference=references.get(p.order_id) if p.order_id else None,
                provider_reference=p.provider_reference,
                failure_reason=p.failure_reason,
                is_simulated=p.is_simulated,
                created_at=p.created_at,
            )
        )
    return out


async def list_payments(
    session: AsyncSession, q: str | None, status: PaymentStatus | None
) -> AdminPaymentList:
    payments, more = await _page(session, _payments_query(q, status), LIMIT)
    return AdminPaymentList(items=await _admin_payments(session, payments), truncated=more)


# --- promo-code activity --------------------------------------------------------------------


async def list_promotions(session: AsyncSession, q: str | None) -> AdminPromotionList:
    """SRS 4.12: every campaign on the platform, newest first, searchable by code, campaign
    name, event title or organizer email. Read-only; the numbers come from the same report
    as the organizer's campaign page."""
    query = (
        select(PromotionalCampaign)
        .join(Event, Event.id == PromotionalCampaign.event_id)
        .join(OrganizerProfile, OrganizerProfile.id == Event.organizer_profile_id)
        .join(User, User.id == OrganizerProfile.user_id)
        .order_by(PromotionalCampaign.created_at.desc())
    )
    if q and q.strip():
        code_match = select(PromoCode.campaign_id).where(_like(PromoCode.code, q))
        query = query.where(
            or_(
                PromotionalCampaign.id.in_(code_match),
                _like(PromotionalCampaign.name, q),
                _like(Event.title, q),
                _like(User.email, q),
            )
        )
    campaigns, more = await _page(session, query, LIMIT)
    items = []
    for campaign in campaigns:
        read = await promotions.to_read(session, campaign)
        event = await session.get_one(Event, campaign.event_id)
        profile = await session.get_one(OrganizerProfile, event.organizer_profile_id)
        owner = await session.get_one(User, profile.user_id)
        items.append(
            AdminPromotion(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                event_id=event.id,
                event_title=event.title,
                organizer_email=owner.email,
                code=read.code,
                status=read.status,
                discount_type=campaign.discount_type,
                discount_percent=campaign.discount_percent,
                discount_kzt=campaign.discount_kzt,
                max_redemptions=read.max_redemptions,
                redeemed_count=read.redeemed_count,
                report=read.report,
                created_at=campaign.created_at,
                disabled_at=campaign.disabled_at,
            )
        )
    return AdminPromotionList(items=items, truncated=more)


# --- reported events ------------------------------------------------------------------------


async def report_event(
    session: AsyncSession, user: User, slug: str, data: ReportCreate
) -> EventReport:
    """Anyone signed in can report an event they can see (SRS 4.12)."""
    from app.services.events import get_public_by_slug

    event = await get_public_by_slug(session, slug, user)
    report = EventReport(
        id=uuid.uuid4(),
        event_id=event.id,
        reporter_user_id=user.id,
        reason=data.reason,
        details=data.details,
        status=EventReportStatus.OPEN,
    )
    try:
        async with session.begin_nested():
            session.add(report)
            await session.flush()
    except IntegrityError as exc:
        raise AppError(
            409, "report_already_open", "You've already reported this event; we're on it."
        ) from exc
    await session.commit()
    return report


async def _admin_reports(
    session: AsyncSession, reports: Sequence[EventReport]
) -> list[AdminReport]:
    events = {
        e.id: e
        for e in await session.scalars(
            select(Event).where(Event.id.in_({r.event_id for r in reports}))
        )
    }
    emails = dict(
        (
            await session.execute(
                select(User.id, User.email).where(
                    User.id.in_({r.reporter_user_id for r in reports})
                )
            )
        )
        .tuples()
        .all()
    )
    return [
        AdminReport(
            id=r.id,
            event_id=r.event_id,
            event_title=events[r.event_id].title,
            event_slug=events[r.event_id].slug,
            event_suspended=events[r.event_id].is_suspended,
            reporter_email=emails[r.reporter_user_id],
            reason=r.reason,
            details=r.details,
            status=r.status,
            created_at=r.created_at,
            reviewed_at=r.reviewed_at,
            review_note=r.review_note,
        )
        for r in reports
    ]


async def list_reports(session: AsyncSession, status: EventReportStatus | None) -> AdminReportList:
    query = select(EventReport)
    if status is not None:
        query = query.where(EventReport.status == status)
    reports, more = await _page(session, query.order_by(EventReport.created_at.desc()), LIMIT)
    return AdminReportList(items=await _admin_reports(session, reports), truncated=more)


async def review_report(
    session: AsyncSession, admin: User, report_id: uuid.UUID, data: ReportReview
) -> AdminReport:
    report = await session.get(EventReport, report_id, with_for_update=True)
    if report is None:
        raise AppError(404, "report_not_found", "Report not found.")
    if report.status is not EventReportStatus.OPEN:
        raise AppError(409, "report_already_reviewed", "This report has already been reviewed.")
    report.reviewed_by_user_id = admin.id
    report.reviewed_at = datetime.now(UTC)
    report.review_note = data.note
    if data.action == "suspend_event":
        report.status = EventReportStatus.ACTIONED
        await session.flush()
        await set_event_suspended(
            session, admin, report.event_id, True, data.note or f"Report: {report.reason.value}"
        )
    else:
        report.status = EventReportStatus.DISMISSED
    audit.record(
        session,
        actor_id=admin.id,
        action="admin.report_actioned"
        if data.action == "suspend_event"
        else "admin.report_dismissed",
        entity_type="event_report",
        entity_id=report.id,
        description=f"Reviewed a '{report.reason.value}' report: {data.action}"
        + (f". Note: {data.note}" if data.note else ""),
        event_id=report.event_id,
    )
    await session.commit()
    (read,) = await _admin_reports(session, [report])
    return read


# --- settings -------------------------------------------------------------------------------


async def read_settings(session: AsyncSession) -> SettingsRead:
    row = await platform_settings.current(session)
    return SettingsRead(
        activation_fee_kzt=await platform_settings.activation_fee_kzt(session),
        customized=row is not None,
        updated_at=row.updated_at if row else None,
    )


async def update_settings(session: AsyncSession, admin: User, data: SettingsUpdate) -> SettingsRead:
    """SRS 4.12 "Configure activation fees". Applies to fees paid from now on."""
    before = await platform_settings.activation_fee_kzt(session)
    row = await platform_settings.current(session)
    if row is None:
        row = PlatformSettings(singleton=True, activation_fee_kzt=data.activation_fee_kzt)
        session.add(row)
    row.activation_fee_kzt = data.activation_fee_kzt
    row.updated_by_user_id = admin.id
    if before != data.activation_fee_kzt:
        audit.record(
            session,
            actor_id=admin.id,
            action="admin.activation_fee_changed",
            entity_type="platform_settings",
            entity_id=None,
            description=f"Activation fee changed from {before} to {data.activation_fee_kzt} KZT",
        )
    await session.commit()
    await session.refresh(row)
    return await read_settings(session)


# --- CSV export (SRS 4.12 "Export basic operational reports") ------------------------------


def _cell(value: object) -> str:
    """A CSV cell that spreadsheet apps won't run as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv(header: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return out.getvalue()


async def export_csv(session: AsyncSession, admin: User, kind: str) -> str:
    if kind == "users":
        users, _ = await _page(session, _users_query(None, None, None), EXPORT_LIMIT)
        body = _csv(
            ["id", "email", "full_name", "role", "email_verified", "suspended", "created_at"],
            (
                [
                    u.id,
                    u.email,
                    u.full_name,
                    u.role.value,
                    u.is_email_verified,
                    u.is_suspended,
                    u.created_at.isoformat(),
                ]
                for u in users
            ),
        )
    elif kind == "events":
        events, _ = await _page(session, _events_query(None, None, None), EXPORT_LIMIT)
        reads = await _admin_events(session, events)
        body = _csv(
            [
                "id",
                "title",
                "status",
                "visibility",
                "suspended",
                "organizer",
                "organizer_email",
                "starts_at",
                "paid_sales",
                "open_reports",
            ],
            (
                [
                    e.id,
                    e.title,
                    e.status.value,
                    e.visibility.value,
                    e.is_suspended,
                    e.organizer_name,
                    e.organizer_email,
                    e.starts_at.isoformat(),
                    e.paid_sales.value if e.paid_sales else "",
                    e.open_reports,
                ]
                for e in reads
            ),
        )
    elif kind == "orders":
        orders, _ = await _page(session, _orders_query(None, None), EXPORT_LIMIT)
        reads_o = await _admin_orders(session, orders)
        body = _csv(
            [
                "id",
                "reference",
                "status",
                "event",
                "buyer_email",
                "total_kzt",
                "refunded_kzt",
                "created_at",
            ],
            (
                [
                    o.id,
                    o.reference,
                    o.status.value,
                    o.event_title,
                    o.buyer_email,
                    o.total_kzt,
                    o.refunded_kzt,
                    o.created_at.isoformat(),
                ]
                for o in reads_o
            ),
        )
    elif kind == "payments":
        payments, _ = await _page(session, _payments_query(None, None), EXPORT_LIMIT)
        reads_p = await _admin_payments(session, payments)
        body = _csv(
            [
                "id",
                "purpose",
                "status",
                "amount_kzt",
                "user_email",
                "event",
                "order_reference",
                "provider_reference",
                "simulated_demo",
                "created_at",
            ],
            (
                [
                    p.id,
                    p.purpose.value,
                    p.status.value,
                    p.amount_kzt,
                    p.user_email,
                    p.event_title,
                    p.order_reference,
                    p.provider_reference,
                    p.is_simulated,
                    p.created_at.isoformat(),
                ]
                for p in reads_p
            ),
        )
    else:
        raise AppError(404, "export_not_found", "Unknown export.")
    audit.record(
        session,
        actor_id=admin.id,
        action="admin.exported",
        entity_type="export",
        entity_id=None,
        description=f"Exported {kind} as CSV",
    )
    await session.commit()
    return body
