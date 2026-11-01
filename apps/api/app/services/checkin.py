"""Check-in (SRS 4.8). Authorization is per event: the organizer who owns it, or a user with
an active StaffAssignment. A platform role alone never grants check-in."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, StaffRole
from app.models import Event, OrganizerProfile, StaffAssignment, User
from app.schemas.checkin import CheckInEvent

# Events stay in the scanner's list until a day after they end (late arrivals, undo).
_GRACE = timedelta(days=1)
_SCANNABLE = (EventStatus.PUBLISHED, EventStatus.UNPUBLISHED)


async def list_events(session: AsyncSession, user: User) -> list[CheckInEvent]:
    cutoff = datetime.now(UTC) - _GRACE
    owned = await session.scalars(
        select(Event)
        .join(OrganizerProfile, OrganizerProfile.id == Event.organizer_profile_id)
        .where(
            OrganizerProfile.user_id == user.id,
            Event.status.in_(_SCANNABLE),
            Event.ends_at > cutoff,
        )
    )
    assigned = (
        (
            await session.execute(
                select(Event, StaffAssignment.role)
                .join(StaffAssignment, StaffAssignment.event_id == Event.id)
                .where(
                    StaffAssignment.user_id == user.id,
                    StaffAssignment.revoked_at.is_(None),
                    Event.status.in_(_SCANNABLE),
                    Event.ends_at > cutoff,
                )
            )
        )
        .tuples()
        .all()
    )

    def item(event: Event, role: Literal["owner", "event_admin", "check_in_staff"]) -> CheckInEvent:
        return CheckInEvent(
            id=event.id,
            title=event.title,
            status=event.status,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            timezone=event.timezone,
            venue_name=event.venue.name if event.venue else None,
            role=role,
            can_undo=role != StaffRole.CHECK_IN_STAFF.value,
        )

    items = {e.id: item(e, "owner") for e in owned}
    for event, role in assigned:
        items.setdefault(
            event.id,
            item(event, "event_admin" if role is StaffRole.EVENT_ADMIN else "check_in_staff"),
        )
    return sorted(items.values(), key=lambda e: e.starts_at)
