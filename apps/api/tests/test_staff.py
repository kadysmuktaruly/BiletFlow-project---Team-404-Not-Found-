"""SRS 4.8 / 2.3: organizers assign Event Admins (check-in staff) to one event."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import API_PREFIX
from app.models import AuditLogEntry, StaffAssignment
from tests.factories import make_event, make_organizer, make_user, organizer_bearer

ORG = f"{API_PREFIX}/organizer/events"


async def test_assign_list_and_revoke_staff(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_event(session, organizer)
    staff = await make_user(session, email="door@example.com", full_name="Door Person")
    await session.commit()
    headers = await organizer_bearer(session, organizer)

    created = await client.post(
        f"{ORG}/{event.id}/staff",
        headers=headers,
        json={"email": "DOOR@example.com", "role": "check_in_staff"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["user_id"] == str(staff.id)
    assert body["role"] == "check_in_staff"
    assert body["full_name"] == "Door Person"

    listed = (await client.get(f"{ORG}/{event.id}/staff", headers=headers)).json()
    assert [s["email"] for s in listed] == ["door@example.com"]

    duplicate = await client.post(
        f"{ORG}/{event.id}/staff", headers=headers, json={"email": staff.email}
    )
    assert duplicate.json()["error"]["code"] == "already_assigned"

    revoked = await client.delete(f"{ORG}/{event.id}/staff/{body['id']}", headers=headers)
    assert revoked.status_code == 204
    assert (await client.get(f"{ORG}/{event.id}/staff", headers=headers)).json() == []
    # The row is kept for the audit trail, and the person can be assigned again.
    assignment = await session.get_one(StaffAssignment, body["id"])
    assert assignment.revoked_at is not None
    again = await client.post(
        f"{ORG}/{event.id}/staff", headers=headers, json={"email": staff.email}
    )
    assert again.status_code == 201

    actions = set(
        await session.scalars(
            select(AuditLogEntry.action_type).where(AuditLogEntry.event_id == event.id)
        )
    )
    assert {"staff.assigned", "staff.revoked"} <= actions


async def test_assign_unknown_or_owner_email(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_event(session, organizer)
    await session.commit()
    headers = await organizer_bearer(session, organizer)
    unknown = await client.post(
        f"{ORG}/{event.id}/staff", headers=headers, json={"email": "nobody@example.com"}
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "user_not_found"
    owner = await client.post(
        f"{ORG}/{event.id}/staff", headers=headers, json={"email": organizer.contact_email}
    )
    assert owner.json()["error"]["code"] == "already_owner"


async def test_only_the_owner_manages_staff(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_event(session, organizer)
    stranger = await make_organizer(session)
    target = await make_user(session)
    await session.commit()
    response = await client.post(
        f"{ORG}/{event.id}/staff",
        headers=await organizer_bearer(session, stranger),
        json={"email": target.email},
    )
    assert response.status_code == 404
