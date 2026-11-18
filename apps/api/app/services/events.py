"""Organizer-side event management (SRS 4.2). Drafts first; publishing comes later."""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivationStatus,
    EventStatus,
    EventVisibility,
    NotificationType,
    OrderStatus,
    TicketStatus,
)
from app.errors import AppError
from app.i18n import normalize_locale
from app.i18n.emails import EVENT_CHANGES
from app.models import (
    Event,
    Order,
    OrganizerProfile,
    PaidSalesActivation,
    Ticket,
    TicketType,
    User,
    Venue,
)
from app.schemas.event import (
    EventCreate,
    EventUpdate,
    OrganizerSummary,
    PublicEventList,
    PublicEventRead,
    VenueInput,
    VenueRead,
    localize,
)
from app.services import audit
from app.services.mail import Outbound
from app.services.notifications import Message, notify_users
from app.slugs import event_slug

# Cancelled and completed events are historical records (SRS 4.16) and stay as they were.
EDITABLE_STATUSES = frozenset({EventStatus.DRAFT, EventStatus.UNPUBLISHED, EventStatus.PUBLISHED})

_SLUG_ATTEMPTS = 5


def _apply_venue(venue: Venue, data: VenueInput) -> None:
    for field, value in data.model_dump().items():
        setattr(venue, field, value)


async def create_draft(
    session: AsyncSession, organizer: OrganizerProfile, data: EventCreate
) -> Event:
    venue = Venue(country_code="KZ", has_seat_map=False, name="", address_line1="", city="")
    _apply_venue(venue, data.venue)
    session.add(venue)
    await session.flush()

    for _ in range(_SLUG_ATTEMPTS):
        event = Event(
            organizer_profile_id=organizer.id,
            venue_id=venue.id,
            title=data.title,
            slug=event_slug(data.title),
            description=data.description,
            category=data.category,
            cover_image_url=str(data.cover_image_url) if data.cover_image_url else None,
            status=EventStatus.DRAFT,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            timezone=data.timezone,
            visibility=data.visibility,
            registration_opens_at=data.registration_opens_at,
            registration_closes_at=data.registration_closes_at,
            capacity=data.capacity,
            refund_policy=data.refund_policy,
        )
        try:
            async with session.begin_nested():
                session.add(event)
                await session.flush()
        except IntegrityError:
            continue  # slug collision; draw a new suffix
        await session.commit()
        await session.refresh(event)
        return event
    raise AppError(500, "internal_error", "Could not allocate an event address.")


async def list_owned(session: AsyncSession, organizer: OrganizerProfile) -> list[Event]:
    result = await session.scalars(
        select(Event)
        .where(Event.organizer_profile_id == organizer.id)
        .order_by(Event.starts_at.desc())
    )
    return list(result)


async def update(
    session: AsyncSession, event: Event, user: User, data: EventUpdate
) -> tuple[Event, Outbound]:
    if event.status not in EDITABLE_STATUSES:
        raise AppError(409, "event_not_editable", "Cancelled or completed events can't be edited.")
    old_capacity, old_visibility = event.capacity, event.visibility
    before = _material(event)

    changes = data.model_dump(
        exclude_unset=True,
        exclude={
            "venue",
            "starts_at",
            "ends_at",
            "registration_opens_at",
            "registration_closes_at",
            "capacity",
        },
    )
    for field in ("title",):
        if field in changes and changes[field] is None:
            del changes[field]  # required columns cannot be cleared
    for field, value in changes.items():
        if field == "cover_image_url" and value is not None:
            value = str(value)
        if field in ("timezone", "visibility") and value is None:
            continue
        setattr(event, field, value)

    tz = ZoneInfo(event.timezone)
    if data.starts_at is not None:
        event.starts_at = localize(data.starts_at, tz)
    if data.ends_at is not None:
        event.ends_at = localize(data.ends_at, tz)
    if event.ends_at < event.starts_at:
        raise AppError(422, "invalid_event_times", "The event must end after it starts.")
    fields = data.model_fields_set
    for name in ("registration_opens_at", "registration_closes_at"):
        if name in fields:
            value = getattr(data, name)
            setattr(event, name, localize(value, tz) if value is not None else None)
    if (
        event.registration_opens_at
        and event.registration_closes_at
        and event.registration_closes_at <= event.registration_opens_at
    ):
        raise AppError(
            422, "invalid_registration_window", "Registration must close after it opens."
        )
    if "capacity" in fields:
        if data.capacity is not None:
            taken = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(TicketType.quantity_sold + TicketType.quantity_reserved), 0
                    )
                ).where(TicketType.event_id == event.id)
            )
            if data.capacity < (taken or 0):
                raise AppError(
                    409,
                    "capacity_below_sold",
                    "The capacity can't be lower than the tickets already sold or reserved.",
                )
        event.capacity = data.capacity
    if event.capacity != old_capacity:
        audit.record(
            session,
            actor_id=user.id,
            action="event.capacity_changed",
            entity_type="event",
            entity_id=event.id,
            description=f"Capacity changed from {old_capacity or 'unlimited'} to "
            f"{event.capacity or 'unlimited'}",
            event_id=event.id,
        )
    if event.visibility is not old_visibility:
        audit.record(
            session,
            actor_id=user.id,
            action="event.visibility_changed",
            entity_type="event",
            entity_id=event.id,
            description=f"Visibility changed from {old_visibility.value} to "
            f"{event.visibility.value}",
            event_id=event.id,
        )

    if data.venue is not None:
        if event.venue is None:
            venue = Venue(country_code="KZ", has_seat_map=False, name="", address_line1="", city="")
            _apply_venue(venue, data.venue)
            session.add(venue)
            await session.flush()
            event.venue_id = venue.id
        else:
            _apply_venue(event.venue, data.venue)

    # SRS 4.10 "Event updates": tell ticket holders when the time, place or name changes.
    outbound: Outbound = []
    await session.flush()
    await session.refresh(event, ["venue"])
    changed = [key for key, value in _material(event).items() if before[key] != value]
    if changed and event.status in (EventStatus.PUBLISHED, EventStatus.UNPUBLISHED):
        outbound = await _notify_holders(session, event, "event_updated", changed)
    await session.commit()
    await session.refresh(event)
    return event, outbound


def _material(event: Event) -> dict[str, object]:
    """The details attendees rely on to turn up: when, where, and what it's called."""
    venue = event.venue
    return {
        "time": (event.starts_at, event.ends_at),
        "venue": (venue.name, venue.address_line1, venue.city) if venue else None,
        "title": event.title,
    }


async def ticket_holders(session: AsyncSession, event_id: uuid.UUID) -> list[User]:
    """Buyers with at least one valid or checked-in ticket for the event."""
    return list(
        await session.scalars(
            select(User)
            .where(
                User.id.in_(
                    select(Order.user_id)
                    .join(Ticket, Ticket.order_id == Order.id)
                    .where(
                        Ticket.event_id == event_id,
                        Ticket.status.in_((TicketStatus.VALID, TicketStatus.CHECKED_IN)),
                    )
                )
            )
            .order_by(User.id)
        )
    )


async def _notify_holders(
    session: AsyncSession,
    event: Event,
    template: str,
    changed: list[str] | None = None,
    holders: list[User] | None = None,
) -> Outbound:
    from app.services.order_emails import format_when

    holders = holders if holders is not None else await ticket_holders(session, event.id)
    venue = event.venue
    where = (
        ", ".join(p for p in (venue.name, venue.address_line1, venue.city) if p) if venue else "—"
    )
    is_update = template == "event_updated"

    def build(holder: User) -> Message:
        labels = EVENT_CHANGES[normalize_locale(holder.locale)]
        return Message(
            type=NotificationType.EVENT_UPDATE
            if is_update
            else NotificationType.EVENT_CANCELLATION,
            template=template,
            params={
                "event": event.title,
                "when": format_when(event),
                "venue": where,
                "changes": ", ".join(labels[c] for c in changed or []),
            },
            action_path=f"/events/{event.slug}" if is_update else "/orders",
            event_id=event.id,
        )

    return await notify_users(session, holders, build)


# --- lifecycle (SRS 4.2: publish, unpublish, cancel) ---------------------------------------


def _log(session: AsyncSession, user: User, event: Event, action: str, description: str) -> None:
    audit.record(
        session,
        actor_id=user.id,
        action=action,
        entity_type="event",
        entity_id=event.id,
        description=description,
        event_id=event.id,
    )


async def publish(session: AsyncSession, event: Event, user: User) -> Event:
    if event.status not in (EventStatus.DRAFT, EventStatus.UNPUBLISHED):
        raise AppError(
            409, "invalid_status_transition", "Only drafts and unpublished events can be published."
        )
    # SRS UC1: the organizer has a verified account.
    if not user.is_email_verified:
        raise AppError(409, "email_not_verified", "Confirm your email address before publishing.")
    if event.venue_id is None:
        raise AppError(409, "venue_required", "Add a venue before publishing.")
    if event.ends_at <= datetime.now(UTC):
        raise AppError(409, "event_in_past", "This event has already ended.")
    has_tickets = await session.scalar(
        select(func.count())
        .select_from(TicketType)
        .where(TicketType.event_id == event.id, TicketType.is_hidden.is_(False))
    )
    if not has_tickets:
        raise AppError(
            409, "no_ticket_types", "Add at least one visible ticket type before publishing."
        )
    event.status = EventStatus.PUBLISHED
    event.published_at = event.published_at or datetime.now(UTC)
    _log(session, user, event, "event.published", f"Published “{event.title}”")
    await session.commit()
    await session.refresh(event)
    return event


async def unpublish(session: AsyncSession, event: Event, user: User) -> Event:
    """Stops new registrations and hides the page. Issued tickets stay valid."""
    if event.status is not EventStatus.PUBLISHED:
        raise AppError(
            409, "invalid_status_transition", "Only published events can be unpublished."
        )
    event.status = EventStatus.UNPUBLISHED
    _log(session, user, event, "event.unpublished", f"Unpublished “{event.title}”")
    await session.commit()
    await session.refresh(event)
    return event


async def cancel(
    session: AsyncSession, event: Event, user: User, reason: str | None
) -> tuple[Event, Outbound]:
    """Cancels the event, every valid ticket and every unpaid order, refunds every paid order
    in full (SRS 4.9, DEMO), and tells every ticket holder (SRS 4.10)."""
    from app.services.orders import OPEN_STATUSES, release_order

    if event.status not in EDITABLE_STATUSES:
        raise AppError(409, "invalid_status_transition", "This event can't be cancelled.")
    await session.refresh(event, with_for_update=True)
    holders = await ticket_holders(session, event.id)
    now = datetime.now(UTC)
    open_orders = await session.scalars(
        select(Order)
        .where(Order.event_id == event.id, Order.status.in_(OPEN_STATUSES))
        .with_for_update()
    )
    for order in open_orders:
        await release_order(session, order, OrderStatus.CANCELLED)
    cancelled = await session.execute(
        sql_update(Ticket)
        .where(Ticket.event_id == event.id, Ticket.status == TicketStatus.VALID)
        .values(status=TicketStatus.CANCELLED, cancelled_at=now)
    )
    event.status = EventStatus.CANCELLED
    event.cancelled_at = now
    event.cancellation_reason = reason
    _log(
        session,
        user,
        event,
        "event.cancelled",
        f"Cancelled “{event.title}”; {cancelled.rowcount} ticket(s) cancelled"  # type: ignore[attr-defined]
        + (f". Reason: {reason}" if reason else ""),
    )
    await session.flush()
    # SRS 4.9: every paid order is refunded in full (DEMO), each buyer told.
    from app.services.refunds import refund_for_event_cancel

    outbound = await refund_for_event_cancel(session, user, event)
    await session.refresh(event, ["venue"])
    outbound += await _notify_holders(session, event, "event_cancelled", holders=holders)
    await session.commit()
    await session.refresh(event)
    return event, outbound


# --- public reads ----------------------------------------------------------------------------

PUBLIC_STATUSES = (EventStatus.PUBLISHED, EventStatus.CANCELLED, EventStatus.COMPLETED)


async def public_read(
    session: AsyncSession, event: Event, *, preview: bool = False
) -> PublicEventRead:
    from app.services.ticket_types import to_public

    organizer = await session.get_one(OrganizerProfile, event.organizer_profile_id)
    types = await session.scalars(
        select(TicketType)
        .where(TicketType.event_id == event.id, TicketType.is_hidden.is_(False))
        .order_by(TicketType.price_kzt, TicketType.created_at)
    )
    activation = await session.scalar(
        select(PaidSalesActivation.status).where(PaidSalesActivation.event_id == event.id)
    )
    now = datetime.now(UTC)
    registration_open = (
        event.status is EventStatus.PUBLISHED
        and not event.is_suspended
        and (event.registration_opens_at is None or event.registration_opens_at <= now)
        and (event.registration_closes_at is None or now < event.registration_closes_at)
        and now < event.ends_at
    )
    return PublicEventRead(
        id=event.id,
        slug=event.slug,
        title=event.title,
        description=event.description,
        category=event.category,
        cover_image_url=event.cover_image_url,
        status=event.status,
        visibility=event.visibility,
        venue=VenueRead.model_validate(event.venue) if event.venue else None,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        timezone=event.timezone,
        registration_opens_at=event.registration_opens_at,
        registration_closes_at=event.registration_closes_at,
        refund_policy=event.refund_policy,
        registration_open=registration_open,
        paid_sales_enabled=activation is ActivationStatus.ACTIVE,
        organizer=OrganizerSummary.model_validate(organizer, from_attributes=True),
        ticket_types=[to_public(t) for t in types],
        preview=preview,
    )


async def get_public_by_slug(session: AsyncSession, slug: str, user: User | None) -> Event:
    """Public and unlisted events open by slug; private ones only for their owner and staff.
    Drafts and unpublished events don't exist for anyone here (404)."""
    from app.services.orders import is_owner_or_staff

    event = await session.scalar(select(Event).where(Event.slug == slug))
    if event is None or event.status not in PUBLIC_STATUSES:
        raise AppError(404, "event_not_found", "Event not found.")
    if event.visibility is EventVisibility.PRIVATE and not await is_owner_or_staff(
        session, event, user
    ):
        raise AppError(404, "event_not_found", "Event not found.")
    return event


async def list_public(
    session: AsyncSession, *, q: str | None, limit: int, offset: int
) -> PublicEventList:
    """SRS 4.2: only published, public, upcoming events are listed. Unlisted and private
    events never appear here."""
    now = datetime.now(UTC)
    where = [
        Event.status == EventStatus.PUBLISHED,
        Event.visibility == EventVisibility.PUBLIC,
        Event.is_suspended.is_(False),
        Event.ends_at > now,
    ]
    if q:
        pattern = f"%{q.strip()}%"
        where.append(Event.title.ilike(pattern) | Event.category.ilike(pattern))
    total = await session.scalar(select(func.count()).select_from(Event).where(*where))
    events = await session.scalars(
        select(Event).where(*where).order_by(Event.starts_at).limit(limit).offset(offset)
    )
    return PublicEventList(items=[await public_read(session, e) for e in events], total=total or 0)
