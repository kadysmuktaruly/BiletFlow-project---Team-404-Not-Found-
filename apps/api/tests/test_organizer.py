"""SRS 4.1: organizers have a profile with contact and payout information."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserRole
from app.main import API_PREFIX
from app.models import OrganizerProfile
from tests.factories import bearer, make_organizer, make_user, organizer_bearer

ORG = f"{API_PREFIX}/organizer"


async def test_organizer_reads_and_updates_profile(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    profile = await make_organizer(session)
    await session.commit()
    user_headers = await organizer_bearer(session, profile)

    got = await client.get(f"{ORG}/profile", headers=user_headers)
    assert got.status_code == 200
    assert got.json()["id"] == str(profile.id)

    updated = await client.put(
        f"{ORG}/profile",
        headers=user_headers,
        json={
            "display_name": "Almaty Jazz Club",
            "contact_email": "hello@jazz.kz",
            "contact_phone": "+77001234567",
            "website_url": "https://jazz.kz",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["display_name"] == "Almaty Jazz Club"
    assert body["website_url"] == "https://jazz.kz/"


async def test_profile_rejects_invalid_contact_email(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    profile = await make_organizer(session)
    await session.commit()
    headers = await organizer_bearer(session, profile)
    response = await client.put(
        f"{ORG}/profile", headers=headers, json={"display_name": "X", "contact_email": "nope"}
    )
    assert response.status_code == 422


async def test_profile_is_created_for_an_organizer_without_one(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, role=UserRole.ORGANIZER)
    await session.commit()
    response = await client.get(f"{ORG}/profile", headers=bearer(user))
    assert response.status_code == 200
    assert response.json()["contact_email"] == user.email
    stored = await session.scalar(
        select(OrganizerProfile).where(OrganizerProfile.user_id == user.id)
    )
    assert stored is not None


async def test_attendees_cannot_use_organizer_endpoints(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    attendee = await make_user(session)
    await session.commit()
    for method, path in (("GET", "/profile"), ("GET", "/events"), ("GET", "/payout-account")):
        response = await client.request(method, f"{ORG}{path}", headers=bearer(attendee))
        assert response.status_code == 403, path


async def test_payout_account_is_simulated_and_stores_last4_only(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    profile = await make_organizer(session)
    await session.commit()
    headers = await organizer_bearer(session, profile)

    assert (await client.get(f"{ORG}/payout-account", headers=headers)).status_code == 404

    full_number = await client.put(
        f"{ORG}/payout-account",
        headers=headers,
        json={"account_holder_name": "A", "bank_name": "Kaspi", "account_last4": "KZ1234567890"},
    )
    assert full_number.status_code == 422

    created = await client.put(
        f"{ORG}/payout-account",
        headers=headers,
        json={
            "account_holder_name": "Aigerim N",
            "bank_name": "Kaspi Bank",
            "account_last4": "4321",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["account_last4"] == "4321"
    assert body["status"] == "verified"
    assert body["is_simulated"] is True
    assert body["demo"] is True

    again = await client.put(
        f"{ORG}/payout-account",
        headers=headers,
        json={"account_holder_name": "Aigerim N", "bank_name": "Halyk", "account_last4": "9999"},
    )
    assert again.json()["id"] == body["id"]  # updated in place, not duplicated
