"""Support cases (SRS 4.13).

**Who sees a case** is decided here, from the case's relationships (SRS 7: "enforced by role
and by relationship to the relevant event, order, or ticket"):

* the requester who opened it;
* for an **attendee case**: the event's organizer and its event admins (`StaffAssignment`
  with role `event_admin`), who answer it;
* for an **organizer case** (an organizer asking the platform): Platform Admins;
* Platform Admins can also open any attendee case (escalations, SRS 4.12).

Anyone else gets 404, as if the case didn't exist. The event of an attendee case is always
derived on the server from the order or ticket, which must be the requester's own.

Messages are polled; there are no sockets (SRS 4.13). Staff can add internal notes that the
requester never sees. Status changes are audited for the event timeline (SRS 4.16) and every
reply, assignment and status change notifies the other side (SRS 4.10).
"""

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    EventStatus,
    EventVisibility,
    NotificationType,
    StaffRole,
    SupportCaseStatus,
    UserRole,
)
from app.errors import AppError
from app.i18n import normalize_locale
from app.i18n.emails import SUPPORT_STATUS
from app.models import (
    Event,
    Order,
    OrganizerProfile,
    StaffAssignment,
    SupportCase,
    SupportMessage,
    Ticket,
    User,
)
from app.schemas.support import (
    CaseContext,
    CaseCreate,
    CaseRead,
    CaseSummary,
    CaseUpdate,
    MessageCreate,
    MessageRead,
    Person,
    ViewerRole,
)
from app.services import audit
from app.services.mail import Outbound
from app.services.notifications import Message, notify_users

_REF_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _not_found() -> AppError:
    return AppError(404, "case_not_found", "Support case not found.")


def _person(user: User) -> Person:
    return Person(id=user.id, full_name=user.full_name)


# --- who handles a case -----------------------------------------------------------------------


async def _platform_admins(session: AsyncSession) -> list[User]:
    return list(
        await session.scalars(
            select(User)
            .where(User.role == UserRole.PLATFORM_ADMIN, User.is_suspended.is_(False))
            .order_by(User.full_name)
        )
    )


async def _event_team(session: AsyncSession, event_id: uuid.UUID) -> list[User]:
    """The event's organizer plus its event admins: the people who answer attendee cases."""
    owner = await session.scalar(
        select(User)
        .join(OrganizerProfile, OrganizerProfile.user_id == User.id)
        .join(Event, Event.organizer_profile_id == OrganizerProfile.id)
        .where(Event.id == event_id)
    )
    admins = list(
        await session.scalars(
            select(User)
            .join(StaffAssignment, StaffAssignment.user_id == User.id)
            .where(
                StaffAssignment.event_id == event_id,
                StaffAssignment.role == StaffRole.EVENT_ADMIN,
                StaffAssignment.revoked_at.is_(None),
            )
            .order_by(User.full_name)
        )
    )
    return ([owner] if owner else []) + [a for a in admins if not owner or a.id != owner.id]


async def handlers(session: AsyncSession, case: SupportCase) -> list[User]:
    """Who may be assigned the case and is told about new requester messages."""
    if case.is_organizer_case or case.event_id is None:
        return await _platform_admins(session)
    return await _event_team(session, case.event_id)


async def _viewer_role(session: AsyncSession, user: User, case: SupportCase) -> ViewerRole | None:
    if case.opened_by_user_id == user.id:
        return "requester"
    return "staff" if await _can_manage(session, user, case) else None


async def _can_manage(session: AsyncSession, user: User, case: SupportCase) -> bool:
    if user.role is UserRole.PLATFORM_ADMIN:
        return True
    if case.is_organizer_case or case.event_id is None:
        return False
    return any(h.id == user.id for h in await _event_team(session, case.event_id))


async def _get_visible(
    session: AsyncSession, user: User, case_id: uuid.UUID, *, lock: bool = False
) -> tuple[SupportCase, ViewerRole]:
    query = select(SupportCase).where(SupportCase.id == case_id)
    if lock:
        query = query.with_for_update()
    case = await session.scalar(query)
    if case is None:
        raise _not_found()
    role = await _viewer_role(session, user, case)
    if role is None:
        raise _not_found()
    return case, role


# --- opening a case ---------------------------------------------------------------------------


async def _unique_reference(session: AsyncSession) -> str:
    for _ in range(10):
        ref = "SC-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(6))
        if not await session.scalar(select(SupportCase.id).where(SupportCase.reference == ref)):
            return ref
    raise AppError(500, "internal_error", "Could not allocate a case reference.")


async def _attendee_context(
    session: AsyncSession, user: User, data: CaseCreate
) -> tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None]:
    """(event_id, order_id, ticket_id), checked to belong to the requester."""
    if data.ticket_id is not None:
        row = (
            await session.execute(
                select(Ticket.id, Ticket.order_id, Ticket.event_id)
                .join(Order, Order.id == Ticket.order_id)
                .where(Ticket.id == data.ticket_id, Order.user_id == user.id)
            )
        ).first()
        if row is None:
            raise AppError(404, "ticket_not_found", "Ticket not found.")
        return row.event_id, row.order_id, row.id
    if data.order_id is not None:
        order = await session.scalar(
            select(Order).where(Order.id == data.order_id, Order.user_id == user.id)
        )
        if order is None:
            raise AppError(404, "order_not_found", "Order not found.")
        return order.event_id, order.id, None
    if data.event_id is not None:
        event = await session.get(Event, data.event_id)
        visible = event is not None and event.status in (
            EventStatus.PUBLISHED,
            EventStatus.CANCELLED,
            EventStatus.COMPLETED,
        )
        if event is not None and visible and event.visibility is EventVisibility.PRIVATE:
            from app.services.orders import is_owner_or_staff

            visible = await is_owner_or_staff(session, event, user)
        if not visible or event is None:
            raise AppError(404, "event_not_found", "Event not found.")
        return event.id, None, None
    raise AppError(422, "case_context_required", "Open a case from an event, an order or a ticket.")


async def create_case(
    session: AsyncSession, user: User, data: CaseCreate
) -> tuple[SupportCase, Outbound]:
    event_id: uuid.UUID | None
    order_id = ticket_id = None
    if data.kind == "organizer":
        if user.role is not UserRole.ORGANIZER:
            raise AppError(403, "forbidden", "Only organizers can open platform support cases.")
        event_id = data.event_id
        if event_id is not None:
            owns = await session.scalar(
                select(Event.id)
                .join(OrganizerProfile, OrganizerProfile.id == Event.organizer_profile_id)
                .where(Event.id == event_id, OrganizerProfile.user_id == user.id)
            )
            if owns is None:
                raise AppError(404, "event_not_found", "Event not found.")
    else:
        event_id, order_id, ticket_id = await _attendee_context(session, user, data)

    now = datetime.now(UTC)
    case = SupportCase(
        id=uuid.uuid4(),
        reference=await _unique_reference(session),
        opened_by_user_id=user.id,
        category=data.category,
        status=SupportCaseStatus.OPEN,
        subject=data.subject.strip(),
        is_organizer_case=data.kind == "organizer",
        event_id=event_id,
        order_id=order_id,
        ticket_id=ticket_id,
        last_message_at=now,
    )
    session.add(case)
    await session.flush()
    session.add(SupportMessage(case_id=case.id, author_user_id=user.id, body=data.message.strip()))
    audit.record(
        session,
        actor_id=user.id,
        action="support_case.opened",
        entity_type="support_case",
        entity_id=case.id,
        description=f"Opened support case {case.reference}: {case.subject}",
        event_id=case.event_id if not case.is_organizer_case else None,
    )
    outbound = await _notify(
        session, case, await handlers(session, case), "support_new_message", exclude=user
    )
    await session.commit()
    return case, outbound


# --- reading ----------------------------------------------------------------------------------


async def _summaries(
    session: AsyncSession, user: User, cases: list[SupportCase]
) -> list[CaseSummary]:
    people = {
        u.id: u
        for u in await session.scalars(
            select(User).where(
                User.id.in_(
                    {c.opened_by_user_id for c in cases}
                    | {c.assigned_to_user_id for c in cases if c.assigned_to_user_id}
                )
            )
        )
    }
    out = []
    for case in cases:
        role = await _viewer_role(session, user, case)
        assert role is not None
        out.append(
            CaseSummary(
                id=case.id,
                reference=case.reference,
                kind="organizer" if case.is_organizer_case else "attendee",
                category=case.category,
                status=case.status,
                subject=case.subject,
                requester=_person(people[case.opened_by_user_id]),
                assigned_to=_person(people[case.assigned_to_user_id])
                if case.assigned_to_user_id
                else None,
                context=await _context(session, case),
                viewer_role=role,
                created_at=case.created_at,
                last_message_at=case.last_message_at,
                resolved_at=case.resolved_at,
            )
        )
    return out


async def _context(session: AsyncSession, case: SupportCase) -> CaseContext:
    event = await session.get(Event, case.event_id) if case.event_id else None
    order = await session.get(Order, case.order_id) if case.order_id else None
    ticket = await session.get(Ticket, case.ticket_id) if case.ticket_id else None
    return CaseContext(
        event_id=case.event_id,
        event_title=event.title if event else None,
        event_slug=event.slug if event else None,
        order_id=case.order_id,
        order_reference=order.reference if order else None,
        ticket_id=case.ticket_id,
        ticket_number=ticket.ticket_number if ticket else None,
    )


async def list_cases(session: AsyncSession, user: User) -> list[CaseSummary]:
    """Cases you opened, plus the ones you handle."""
    query = select(SupportCase)
    if user.role is not UserRole.PLATFORM_ADMIN:
        team_events = (
            select(Event.id)
            .join(OrganizerProfile, OrganizerProfile.id == Event.organizer_profile_id)
            .where(OrganizerProfile.user_id == user.id)
            .union(
                select(StaffAssignment.event_id).where(
                    StaffAssignment.user_id == user.id,
                    StaffAssignment.role == StaffRole.EVENT_ADMIN,
                    StaffAssignment.revoked_at.is_(None),
                )
            )
        )
        query = query.where(
            or_(
                SupportCase.opened_by_user_id == user.id,
                (SupportCase.is_organizer_case.is_(False)) & SupportCase.event_id.in_(team_events),
            )
        )
    cases = list(
        await session.scalars(
            query.order_by(
                SupportCase.last_message_at.desc().nulls_last(), SupportCase.created_at.desc()
            ).limit(200)
        )
    )
    return await _summaries(session, user, cases)


async def read_case(session: AsyncSession, user: User, case_id: uuid.UUID) -> CaseRead:
    case, role = await _get_visible(session, user, case_id)
    can_manage = await _can_manage(session, user, case)
    query = select(SupportMessage).where(SupportMessage.case_id == case.id)
    if not can_manage:
        # SRS 4.13: internal notes are for the handling side only.
        query = query.where(SupportMessage.is_internal_note.is_(False))
    messages = list(
        await session.scalars(query.order_by(SupportMessage.created_at, SupportMessage.id))
    )
    authors = {
        u.id: u
        for u in await session.scalars(
            select(User).where(User.id.in_({m.author_user_id for m in messages}))
        )
    }
    (summary,) = await _summaries(session, user, [case])
    return CaseRead(
        **summary.model_dump(),
        messages=[
            MessageRead(
                id=m.id,
                author=_person(authors[m.author_user_id]),
                from_staff=m.author_user_id != case.opened_by_user_id,
                body=m.body,
                internal=m.is_internal_note,
                created_at=m.created_at,
            )
            for m in messages
        ],
        can_manage=can_manage,
        assignees=[_person(h) for h in await handlers(session, case)] if can_manage else [],
    )


# --- replying and managing -------------------------------------------------------------------


async def add_message(
    session: AsyncSession, user: User, case_id: uuid.UUID, data: MessageCreate
) -> tuple[SupportCase, Outbound]:
    case, role = await _get_visible(session, user, case_id, lock=True)
    can_manage = await _can_manage(session, user, case)
    if data.internal and not can_manage:
        raise AppError(403, "forbidden", "Only staff can add internal notes.")
    now = datetime.now(UTC)
    session.add(
        SupportMessage(
            case_id=case.id,
            author_user_id=user.id,
            body=data.body.strip(),
            is_internal_note=data.internal,
        )
    )
    case.last_message_at = now
    outbound: Outbound = []
    if role == "requester":
        # The requester answered: a waiting or resolved case goes back into the queue.
        if case.status is SupportCaseStatus.WAITING_FOR_CUSTOMER:
            await _set_status(session, user, case, SupportCaseStatus.IN_PROGRESS, notify=False)
        elif case.status is SupportCaseStatus.RESOLVED:
            await _set_status(session, user, case, SupportCaseStatus.OPEN, notify=False)
        assignee = (
            await session.get(User, case.assigned_to_user_id) if case.assigned_to_user_id else None
        )
        recipients = [assignee] if assignee else await handlers(session, case)
        outbound = await _notify(session, case, recipients, "support_new_message", exclude=user)
    elif not data.internal:
        requester = await session.get_one(User, case.opened_by_user_id)
        outbound = await _notify(session, case, [requester], "support_new_message", exclude=user)
    await session.commit()
    return case, outbound


async def update_case(
    session: AsyncSession, user: User, case_id: uuid.UUID, data: CaseUpdate
) -> tuple[SupportCase, Outbound]:
    case, _ = await _get_visible(session, user, case_id, lock=True)
    if not await _can_manage(session, user, case):
        raise AppError(403, "forbidden", "Only the people handling this case can change it.")
    outbound: Outbound = []
    if "assigned_to_user_id" in data.model_fields_set and (
        data.assigned_to_user_id != case.assigned_to_user_id
    ):
        assignee_name = "nobody"
        if data.assigned_to_user_id is None:
            case.assigned_to_user_id = None
            case.assigned_at = None
        else:
            team = {h.id: h for h in await handlers(session, case)}
            assignee = team.get(data.assigned_to_user_id)
            if assignee is None:
                raise AppError(422, "invalid_assignee", "That person can't handle this case.")
            case.assigned_to_user_id = assignee.id
            case.assigned_at = datetime.now(UTC)
            assignee_name = assignee.full_name
            outbound += await _notify(
                session, case, [assignee], "support_case_assigned", exclude=user
            )
        audit.record(
            session,
            actor_id=user.id,
            action="support_case.assigned",
            entity_type="support_case",
            entity_id=case.id,
            description=f"Support case {case.reference} assigned to {assignee_name}",
            event_id=None if case.is_organizer_case else case.event_id,
        )
    if data.status is not None and data.status is not case.status:
        outbound += await _set_status(session, user, case, data.status, notify=True)
    await session.commit()
    return case, outbound


async def _set_status(
    session: AsyncSession,
    actor: User,
    case: SupportCase,
    status: SupportCaseStatus,
    *,
    notify: bool,
) -> Outbound:
    old = case.status
    case.status = status
    case.resolved_at = datetime.now(UTC) if status is SupportCaseStatus.RESOLVED else None
    # SRS 4.16 lists support-case status changes on the event timeline.
    audit.record(
        session,
        actor_id=actor.id,
        action="support_case.status_changed",
        entity_type="support_case",
        entity_id=case.id,
        description=f"Support case {case.reference}: {old.value} → {status.value}",
        event_id=None if case.is_organizer_case else case.event_id,
    )
    if not notify:
        return []
    requester = await session.get_one(User, case.opened_by_user_id)
    return await _notify(session, case, [requester], "support_status_changed", exclude=actor)


async def _notify(
    session: AsyncSession,
    case: SupportCase,
    recipients: list[User],
    template: str,
    *,
    exclude: User,
) -> Outbound:
    types = {
        "support_new_message": NotificationType.SUPPORT_NEW_MESSAGE,
        "support_case_assigned": NotificationType.SUPPORT_CASE_ASSIGNED,
        "support_status_changed": NotificationType.SUPPORT_STATUS_CHANGE,
    }

    def build(recipient: User) -> Message:
        locale = normalize_locale(recipient.locale)
        return Message(
            type=types[template],
            template=template,
            params={
                "reference": case.reference,
                "subject": case.subject,
                "status": SUPPORT_STATUS[locale][case.status.value],
            },
            action_path=f"/support/{case.id}",
            event_id=case.event_id,
            order_id=case.order_id,
            ticket_id=case.ticket_id,
        )

    return await notify_users(session, [r for r in recipients if r.id != exclude.id], build)
