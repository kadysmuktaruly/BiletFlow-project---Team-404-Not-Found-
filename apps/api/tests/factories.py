"""Small builders for arranging test data directly in the database.

They flush but do not commit, so a test can build a graph and commit once. Defaults are
valid and unique; pass keyword arguments to override any column.
"""

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, UserRole
from app.models import Event, OrganizerProfile, TicketType, User
from app.security import TokenType, create_token, hash_password

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


DEFAULT_PASSWORD = "correct-horse-battery"


def bearer(user: User) -> dict[str, str]:
    """Authorization header for `user`, without going through /auth/login."""
    return {"Authorization": f"Bearer {create_token(TokenType.ACCESS, user.id)}"}


async def organizer_bearer(session: AsyncSession, profile: OrganizerProfile) -> dict[str, str]:
    """Authorization header for the user who owns `profile`."""
    return bearer(await session.get_one(User, profile.user_id))


async def make_user(
    session: AsyncSession, password: str = DEFAULT_PASSWORD, **overrides: Any
) -> User:
    n = _n()
    values: dict[str, Any] = {
        "email": f"user{n}@example.com",
        "hashed_password": await hash_password(password),
        "full_name": f"Test User {n}",
        "role": UserRole.ATTENDEE,
        "is_email_verified": True,
    }
    values.update(overrides)
    user = User(**values)
    session.add(user)
    await session.flush()
    return user


async def make_organizer(session: AsyncSession, **user_overrides: Any) -> OrganizerProfile:
    user = await make_user(session, role=UserRole.ORGANIZER, **user_overrides)
    profile = OrganizerProfile(
        user_id=user.id, display_name=user.full_name, contact_email=user.email
    )
    session.add(profile)
    await session.flush()
    return profile


async def make_event(session: AsyncSession, organizer: OrganizerProfile, **overrides: Any) -> Event:
    n = _n()
    starts = datetime.now(UTC) + timedelta(days=30)
    values: dict[str, Any] = {
        "organizer_profile_id": organizer.id,
        "title": f"Test Event {n}",
        "slug": f"test-event-{n}",
        "status": EventStatus.DRAFT,
        "starts_at": starts,
        "ends_at": starts + timedelta(hours=3),
        "timezone": "Asia/Almaty",
    }
    values.update(overrides)
    event = Event(**values)
    session.add(event)
    await session.flush()
    return event


async def make_ticket_type(session: AsyncSession, event: Event, **overrides: Any) -> TicketType:
    n = _n()
    values: dict[str, Any] = {
        "event_id": event.id,
        "name": f"Ticket type {n}",
        "price_kzt": 0,
        "quantity_total": 100,
        "max_per_order": 10,
    }
    values.update(overrides)
    ticket_type = TicketType(**values)
    session.add(ticket_type)
    await session.flush()
    return ticket_type


async def make_published_event(
    session: AsyncSession, organizer: OrganizerProfile | None = None, **overrides: Any
) -> Event:
    """A published, public event, open for registration."""
    organizer = organizer or await make_organizer(session)
    overrides.setdefault("status", EventStatus.PUBLISHED)
    overrides.setdefault("published_at", datetime.now(UTC))
    return await make_event(session, organizer, **overrides)
