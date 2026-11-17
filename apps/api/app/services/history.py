"""Organizer event history (SRS 4.16): the activity timeline and duplicating an event.

* **Who may see the timeline:** the event's organizer, its event admins, and Platform
  Admins (moderation, support). Anyone else gets 404 — the same event-level rule as the
  records themselves (SRS 7). It reads the append-only audit log; nothing here can edit it.
* **Duplicating** copies the configuration into a new draft: details, venue, visibility,
  capacity, refund policy and ticket types. Never orders, tickets, payments, check-ins,
  support cases, campaigns (their codes are unique) or paid-sales activation (it is
  per event, SRS 4.5). A past event's dates move forward by whole weeks, so the copy keeps
  its weekday and time and lands in the future.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, StaffRole, UserRole
from app.errors import AppError
from app.models import (
    AuditLogEntry,
    Event,
    OrganizerProfile,
    StaffAssignment,
    TicketType,
    User,
    Venue,
)
from app.schemas.history import Timeline, TimelineEntry
from app.services import audit
from app.slugs import event_slug

TIMELINE_LIMIT = 500


async def _can_view(session: AsyncSession, user: User, event: Event) -> bool:
    if user.role is UserRole.PLATFORM_ADMIN:
        return True
    owner = await session.scalar(
        select(OrganizerProfile.user_id).where(OrganizerProfile.id == event.organizer_profile_id)
    )
    if owner == user.id:
        return True
    return bool(
        await session.scalar(
            select(StaffAssignment.id).where(
                StaffAssignment.event_id == event.id,
                StaffAssignment.user_id == user.id,
                StaffAssignment.role == StaffRole.EVENT_ADMIN,
                StaffAssignment.revoked_at.is_(None),
            )
        )
    )


async def timeline(
    session: AsyncSession,
    user: User,
    event_id: uuid.UUID,
    *,
    date_from: date | None,
    date_to: date | None,
    category: str | None,
) -> Timeline:
    event = await session.get(Event, event_id)
    if event is None or not await _can_view(session, user, event):
        raise AppError(404, "event_not_found", "Event not found.")
    zone = ZoneInfo(event.timezone)
    query = select(AuditLogEntry).where(AuditLogEntry.event_id == event.id)
    if date_from is not None:
        query = query.where(
            AuditLogEntry.occurred_at >= datetime.combine(date_from, time.min, zone)
        )
    if date_to is not None:
        query = query.where(
            AuditLogEntry.occurred_at
            < datetime.combine(date_to + timedelta(days=1), time.min, zone)
        )
    if category:
        query = query.where(AuditLogEntry.action_type.like(f"{category}.%"))
    rows = list(
        await session.scalars(
            query.order_by(AuditLogEntry.occurred_at.desc(), AuditLogEntry.id).limit(
                TIMELINE_LIMIT + 1
            )
        )
    )
    entries = rows[:TIMELINE_LIMIT]
    names = dict(
        (
            await session.execute(
                select(User.id, User.full_name).where(
                    User.id.in_({e.actor_user_id for e in entries if e.actor_user_id})
                )
            )
        )
        .tuples()
        .all()
    )
    categories = sorted(
        set(
            await session.scalars(
                select(func.split_part(AuditLogEntry.action_type, ".", 1))
                .where(AuditLogEntry.event_id == event.id)
                .distinct()
            )
        )
    )
    return Timeline(
        entries=[
            TimelineEntry(
                id=e.id,
                occurred_at=e.occurred_at,
                actor_name=names.get(e.actor_user_id) if e.actor_user_id else None,
                action=e.action_type,
                category=e.action_type.split(".", 1)[0],
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                description=e.description,
            )
            for e in entries
        ],
        categories=categories,
        truncated=len(rows) > TIMELINE_LIMIT,
    )


def _shift(event: Event, now: datetime) -> timedelta:
    """Whole weeks that move the event's start into the future (zero if it already is).
    Computed in the event's zone so the local weekday and time stay the same."""
    if event.starts_at > now:
        return timedelta(0)
    weeks = (now - event.starts_at).days // 7 + 1
    return timedelta(weeks=weeks)


def _moved(value: datetime | None, by: timedelta, zone: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    local = value.astimezone(zone).replace(tzinfo=None) + by
    return local.replace(tzinfo=zone).astimezone(UTC)


async def duplicate(
    session: AsyncSession, source: Event, organizer: OrganizerProfile, user: User
) -> Event:
    """SRS 4.16 / UC12: a new draft with the same configuration, no transactions."""
    now = datetime.now(UTC)
    zone = ZoneInfo(source.timezone)
    by = _shift(source, now)
    venue_id = None
    if source.venue_id is not None:
        original = await session.get_one(Venue, source.venue_id)
        copy = Venue(
            **{
                c.key: getattr(original, c.key)
                for c in Venue.__table__.columns
                if c.key not in ("id", "created_at", "updated_at")
            }
        )
        session.add(copy)
        await session.flush()
        venue_id = copy.id

    for _ in range(5):
        event = Event(
            organizer_profile_id=organizer.id,
            venue_id=venue_id,
            title=source.title,
            slug=event_slug(source.title),
            description=source.description,
            category=source.category,
            cover_image_url=source.cover_image_url,
            status=EventStatus.DRAFT,
            visibility=source.visibility,
            seating_mode=source.seating_mode,
            starts_at=_moved(source.starts_at, by, zone),
            ends_at=_moved(source.ends_at, by, zone),
            timezone=source.timezone,
            registration_opens_at=_moved(source.registration_opens_at, by, zone),
            registration_closes_at=_moved(source.registration_closes_at, by, zone),
            capacity=source.capacity,
            refund_policy=source.refund_policy,
            duplicated_from_event_id=source.id,
        )
        try:
            async with session.begin_nested():
                session.add(event)
                await session.flush()
            break
        except IntegrityError:
            continue
    else:
        raise AppError(500, "internal_error", "Could not allocate an event address.")

    types = await session.scalars(
        select(TicketType).where(TicketType.event_id == source.id).order_by(TicketType.created_at)
    )
    for tt in types:
        session.add(
            TicketType(
                event_id=event.id,
                name=tt.name,
                description=tt.description,
                price_kzt=tt.price_kzt,
                quantity_total=tt.quantity_total,
                quantity_sold=0,
                quantity_reserved=0,
                max_per_order=tt.max_per_order,
                sales_start_at=_moved(tt.sales_start_at, by, zone),
                sales_end_at=_moved(tt.sales_end_at, by, zone),
                is_hidden=tt.is_hidden,
            )
        )
    for target, verb in ((event, "created as a copy of"), (source, "duplicated into")):
        audit.record(
            session,
            actor_id=user.id,
            action="event.duplicated",
            entity_type="event",
            entity_id=event.id,
            description=f"“{target.title}” {verb} a new draft"
            if target is source
            else f"Draft {verb} “{source.title}”",
            event_id=target.id,
        )
    await session.commit()
    await session.refresh(event)
    return event
