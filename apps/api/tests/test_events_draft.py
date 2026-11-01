"""SRS 4.2 (drafts): an organizer creates and edits an event; nobody else can see it."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus
from app.main import API_PREFIX
from tests.factories import bearer, make_event, make_organizer, make_user, organizer_bearer

EVENTS = f"{API_PREFIX}/organizer/events"


def _draft(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Наурыз концерті",
        "description": "Spring concert",
        "category": "music",
        "venue": {"name": "Palace of the Republic", "address_line1": "Dostyk 56", "city": "Almaty"},
        "starts_at": "2026-12-20T19:00",
        "ends_at": "2026-12-20T22:00",
        "timezone": "Asia/Almaty",
    }
    body.update(overrides)
    return body


async def test_create_draft_reads_naive_times_in_event_timezone(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    await session.commit()
    response = await client.post(
        EVENTS, json=_draft(), headers=await organizer_bearer(session, organizer)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["timezone"] == "Asia/Almaty"
    # Kazakhstan is UTC+5 nationwide since March 2024: 19:00 local is 14:00 UTC.
    assert datetime.fromisoformat(body["starts_at"]) == datetime(2026, 12, 20, 14, 0, tzinfo=UTC)
    assert body["starts_at_local"] == "2026-12-20T19:00"
    assert body["venue"]["city"] == "Almaty"
    assert body["slug"].startswith("nauryz-kontserti-")


async def test_server_decides_slug_status_and_owner(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    other = await make_organizer(session)
    await session.commit()
    response = await client.post(
        EVENTS,
        json=_draft(
            slug="my-own-slug",
            status="published",
            organizer_profile_id=str(other.id),
        ),
        headers=await organizer_bearer(session, organizer),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] != "my-own-slug"
    assert body["status"] == "draft"
    # It belongs to the caller: visible to them, invisible to the profile they named.
    mine = await client.get(
        f"{EVENTS}/{body['id']}", headers=await organizer_bearer(session, organizer)
    )
    assert mine.status_code == 200
    theirs = await client.get(
        f"{EVENTS}/{body['id']}", headers=await organizer_bearer(session, other)
    )
    assert theirs.status_code == 404


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"timezone": "Mars/Olympus"}, "timezone"),
        ({"timezone": "+05:00"}, "timezone"),
        ({"ends_at": "2026-12-20T18:00"}, None),
        ({"title": ""}, "title"),
    ],
)
async def test_create_draft_validation(
    client: httpx.AsyncClient,
    session: AsyncSession,
    overrides: dict[str, Any],
    field: str | None,
) -> None:
    organizer = await make_organizer(session)
    await session.commit()
    response = await client.post(
        EVENTS, json=_draft(**overrides), headers=await organizer_bearer(session, organizer)
    )
    assert response.status_code == 422
    if field:
        assert any(field in d["loc"] for d in response.json()["error"]["details"])


async def test_list_shows_only_own_events(client: httpx.AsyncClient, session: AsyncSession) -> None:
    mine = await make_organizer(session)
    theirs = await make_organizer(session)
    own = await make_event(session, mine)
    await make_event(session, theirs)
    await session.commit()
    response = await client.get(EVENTS, headers=await organizer_bearer(session, mine))
    assert [e["id"] for e in response.json()] == [str(own.id)]


async def test_other_organizers_and_attendees_get_404_or_403(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    owner = await make_organizer(session)
    stranger = await make_organizer(session)
    attendee = await make_user(session)
    event = await make_event(session, owner)
    await session.commit()

    for method in ("GET", "PATCH"):
        response = await client.request(
            method,
            f"{EVENTS}/{event.id}",
            json={"title": "Hijacked"} if method == "PATCH" else None,
            headers=await organizer_bearer(session, stranger),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "event_not_found"
    assert (await client.get(f"{EVENTS}/{event.id}", headers=bearer(attendee))).status_code == 403


async def test_edit_draft(client: httpx.AsyncClient, session: AsyncSession) -> None:
    organizer = await make_organizer(session)
    await session.commit()
    headers = await organizer_bearer(session, organizer)
    created = (await client.post(EVENTS, json=_draft(), headers=headers)).json()

    response = await client.patch(
        f"{EVENTS}/{created['id']}",
        headers=headers,
        json={
            "title": "Spring Concert",
            "starts_at": "2026-12-21T18:30",
            "ends_at": "2026-12-21T21:00",
            "venue": {"name": "Kazakhconcert", "address_line1": "Mangilik El 10", "city": "Astana"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Spring Concert"
    assert body["starts_at_local"] == "2026-12-21T18:30"
    assert body["venue"]["city"] == "Astana"
    assert body["venue"]["id"] == created["venue"]["id"]
    assert body["slug"] == created["slug"]  # the address stays stable when the title changes


async def test_edit_rejects_end_before_start(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_event(session, organizer)
    await session.commit()
    response = await client.patch(
        f"{EVENTS}/{event.id}",
        json={"ends_at": "2020-01-01T00:00:00Z"},
        headers=await organizer_bearer(session, organizer),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_event_times"


async def test_cancelled_event_cannot_be_edited(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_event(session, organizer, status=EventStatus.CANCELLED)
    await session.commit()
    response = await client.patch(
        f"{EVENTS}/{event.id}",
        json={"title": "New"},
        headers=await organizer_bearer(session, organizer),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_not_editable"
