"""Organizer-side event management (SRS 4.2). Drafts first; publishing comes later."""

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus
from app.errors import AppError
from app.models import Event, OrganizerProfile, Venue
from app.schemas.event import EventCreate, EventUpdate, VenueInput, localize
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


async def update(session: AsyncSession, event: Event, data: EventUpdate) -> Event:
    if event.status not in EDITABLE_STATUSES:
        raise AppError(409, "event_not_editable", "Cancelled or completed events can't be edited.")

    changes = data.model_dump(exclude_unset=True, exclude={"venue", "starts_at", "ends_at"})
    for field in ("title",):
        if field in changes and changes[field] is None:
            del changes[field]  # required columns cannot be cleared
    for field, value in changes.items():
        if field == "cover_image_url" and value is not None:
            value = str(value)
        if field == "timezone" and value is None:
            continue
        setattr(event, field, value)

    tz = ZoneInfo(event.timezone)
    if data.starts_at is not None:
        event.starts_at = localize(data.starts_at, tz)
    if data.ends_at is not None:
        event.ends_at = localize(data.ends_at, tz)
    if event.ends_at < event.starts_at:
        raise AppError(422, "invalid_event_times", "The event must end after it starts.")

    if data.venue is not None:
        if event.venue is None:
            venue = Venue(country_code="KZ", has_seat_map=False, name="", address_line1="", city="")
            _apply_venue(venue, data.venue)
            session.add(venue)
            await session.flush()
            event.venue_id = venue.id
        else:
            _apply_venue(event.venue, data.venue)

    await session.commit()
    await session.refresh(event)
    return event
