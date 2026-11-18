"""SRS 4.8: an Event Admin signs in and sees only the events they're assigned to."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, StaffRole
from app.main import API_PREFIX
from app.models import StaffAssignment
from tests.factories import (
    bearer,
    make_organizer,
    make_published_event,
    make_user,
    organizer_bearer,
)


async def test_checkin_events_lists_only_assignments(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    mine = await make_published_event(session, organizer, title="Assigned gig")
    as_staff = await make_published_event(session, organizer, title="Scan-only gig")
    await make_published_event(session, organizer, title="Someone else's gig")
    revoked = await make_published_event(session, organizer, title="Revoked gig")
    draft = await make_published_event(session, organizer, title="Draft", status=EventStatus.DRAFT)
    long_ago = datetime.now(UTC) - timedelta(days=10)
    past = await make_published_event(
        session,
        organizer,
        title="Past gig",
        starts_at=long_ago,
        ends_at=long_ago + timedelta(hours=2),
    )
    staff = await make_user(session)
    owner_user_id = organizer.user_id
    for event, role, gone in (
        (mine, StaffRole.EVENT_ADMIN, False),
        (as_staff, StaffRole.CHECK_IN_STAFF, False),
        (revoked, StaffRole.EVENT_ADMIN, True),
        (draft, StaffRole.EVENT_ADMIN, False),
        (past, StaffRole.EVENT_ADMIN, False),
    ):
        session.add(
            StaffAssignment(
                event_id=event.id,
                user_id=staff.id,
                role=role,
                assigned_by_user_id=owner_user_id,
                revoked_at=datetime.now(UTC) if gone else None,
            )
        )
    stranger = await make_user(session)
    await session.commit()

    body = (await client.get(f"{API_PREFIX}/checkin/events", headers=bearer(staff))).json()
    assert {e["title"]: (e["role"], e["can_undo"]) for e in body} == {
        "Assigned gig": ("event_admin", True),
        "Scan-only gig": ("check_in_staff", False),
    }
    assert (await client.get(f"{API_PREFIX}/checkin/events", headers=bearer(stranger))).json() == []


async def test_organizer_sees_own_events_as_owner(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    await make_published_event(session, organizer, title="My gig")
    await session.commit()
    body = (
        await client.get(
            f"{API_PREFIX}/checkin/events", headers=await organizer_bearer(session, organizer)
        )
    ).json()
    assert [(e["title"], e["role"]) for e in body] == [("My gig", "owner")]


async def test_checkin_events_requires_sign_in(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"{API_PREFIX}/checkin/events")).status_code == 401
