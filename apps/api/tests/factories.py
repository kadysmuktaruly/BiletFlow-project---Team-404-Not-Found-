"""Small builders for arranging test data directly in the database.

They flush but do not commit, so a test can build a graph and commit once. Defaults are
valid and unique; pass keyword arguments to override any column.
"""

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, UserRole
from app.models import Event, OrganizerProfile, User
from app.security import TokenType, create_token, hash_password

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


DEFAULT_PASSWORD = "correct-horse-battery"


def bearer(user: User) -> dict[str, str]:
    """Authorization header for `user`, without going through /auth/login."""
    return {"Authorization": f"Bearer {create_token(TokenType.ACCESS, user.id)}"}


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
