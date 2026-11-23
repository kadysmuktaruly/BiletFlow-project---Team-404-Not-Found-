"""PUT /me/role: switching between attendee and organizer."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, UserRole
from app.models import AuditLogEntry, OrganizerProfile, User
from tests.factories import bearer, make_event, make_organizer, make_user

ROLE = "/api/v1/me/role"
ORGANIZER_PROFILE = "/api/v1/organizer/profile"


async def _profiles(session: AsyncSession, user: User) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(OrganizerProfile)
        .where(OrganizerProfile.user_id == user.id)
    )
    return count or 0


async def test_attendee_becomes_organizer_with_a_profile(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session)
    await session.commit()
    headers = bearer(user)
    assert (await client.get(ORGANIZER_PROFILE, headers=headers)).status_code == 403

    response = await client.put(ROLE, json={"role": "organizer"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "organizer"
    assert await _profiles(session, user) == 1

    profile = await client.get(ORGANIZER_PROFILE, headers=headers)
    assert profile.status_code == 200
    assert profile.json()["display_name"] == user.full_name

    entry = await session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action_type == "user.role_changed")
    )
    assert entry is not None
    assert entry.actor_user_id == user.id
    assert entry.description == "attendee → organizer"


async def test_organizer_switches_to_attendee_and_back_keeping_the_profile(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    profile = await make_organizer(session)
    # Drafts and finished events don't need anyone to manage them.
    await make_event(session, profile, status=EventStatus.DRAFT)
    await make_event(session, profile, status=EventStatus.CANCELLED)
    user = await session.get_one(User, profile.user_id)
    await session.commit()
    headers = bearer(user)

    response = await client.put(ROLE, json={"role": "attendee"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "attendee"
    assert (await client.get(ORGANIZER_PROFILE, headers=headers)).status_code == 403
    assert await _profiles(session, user) == 1

    response = await client.put(ROLE, json={"role": "organizer"}, headers=headers)
    assert response.status_code == 200
    assert await _profiles(session, user) == 1
    assert (await client.get(ORGANIZER_PROFILE, headers=headers)).json()["id"] == str(profile.id)


@pytest.mark.parametrize("status", [EventStatus.PUBLISHED, EventStatus.UNPUBLISHED])
async def test_live_events_block_switching_to_attendee(
    client: httpx.AsyncClient, session: AsyncSession, status: EventStatus
) -> None:
    profile = await make_organizer(session)
    await make_event(session, profile, status=status)
    user = await session.get_one(User, profile.user_id)
    await session.commit()

    response = await client.put(ROLE, json={"role": "attendee"}, headers=bearer(user))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "organizer_has_active_events"
    await session.refresh(user)
    assert user.role is UserRole.ORGANIZER


async def test_choosing_the_current_role_changes_nothing(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session)
    await session.commit()

    response = await client.put(ROLE, json={"role": "attendee"}, headers=bearer(user))
    assert response.status_code == 200
    assert response.json()["role"] == "attendee"
    assert await session.scalar(select(func.count()).select_from(AuditLogEntry)) == 0


@pytest.mark.parametrize("role", [UserRole.PLATFORM_ADMIN, UserRole.EVENT_ADMIN])
async def test_appointed_roles_cannot_switch(
    client: httpx.AsyncClient, session: AsyncSession, role: UserRole
) -> None:
    user = await make_user(session, role=role)
    await session.commit()

    response = await client.put(ROLE, json={"role": "organizer"}, headers=bearer(user))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_change_not_allowed"
    await session.refresh(user)
    assert user.role is role


@pytest.mark.parametrize("role", ["platform_admin", "event_admin", "ORGANIZER"])
async def test_only_self_service_roles_can_be_chosen(
    client: httpx.AsyncClient, session: AsyncSession, role: str
) -> None:
    user = await make_user(session)
    await session.commit()

    response = await client.put(ROLE, json={"role": role}, headers=bearer(user))
    assert response.status_code == 422
    await session.refresh(user)
    assert user.role is UserRole.ATTENDEE


async def test_role_change_requires_sign_in(client: httpx.AsyncClient) -> None:
    response = await client.put(ROLE, json={"role": "organizer"})
    assert response.status_code == 401
