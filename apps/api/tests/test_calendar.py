"""Calendar export: GET /events/{slug}/calendar.ics keeps the event's local time."""

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, EventVisibility
from app.main import API_PREFIX
from app.models import User, Venue
from app.services.calendar import _fold
from tests.factories import bearer, make_organizer, make_published_event, make_user

# 19:00 in Almaty (UTC+5) is 14:00 UTC.
STARTS = datetime(2026, 12, 20, 14, 0, tzinfo=UTC)
ENDS = datetime(2026, 12, 20, 17, 0, tzinfo=UTC)


def _unfold(body: str) -> list[str]:
    return body.replace("\r\n ", "").split("\r\n")


async def test_ics_uses_the_event_time_zone(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    venue = Venue(name="Esentai Hall", address_line1="Al-Farabi Ave 77/8", city="Almaty")
    session.add(venue)
    await session.flush()
    event = await make_published_event(
        session,
        title="Jazz, live; at night",
        description="Line one\nLine two",
        venue_id=venue.id,
        starts_at=STARTS,
        ends_at=ENDS,
    )
    await session.commit()

    r = await client.get(f"{API_PREFIX}/events/{event.slug}/calendar.ics", params={"lang": "ru"})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert f'filename="{event.slug}.ics"' in r.headers["content-disposition"]
    lines = _unfold(r.text)
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-2] == "END:VCALENDAR"
    assert "TZID:Asia/Almaty" in lines
    assert "TZOFFSETTO:+0500" in lines
    assert "DTSTART;TZID=Asia/Almaty:20261220T190000" in lines
    assert "DTEND;TZID=Asia/Almaty:20261220T220000" in lines
    assert "SUMMARY:Jazz\\, live\\; at night" in lines
    assert "LOCATION:Esentai Hall\\, Al-Farabi Ave 77/8\\, Almaty" in lines
    assert "STATUS:CONFIRMED" in lines
    assert f"URL:http://localhost:3000/ru/events/{event.slug}" in lines
    assert any(line.startswith("DESCRIPTION:Line one\\nLine two") for line in lines)
    assert all(len(line.encode()) <= 75 for line in r.text.split("\r\n"))


async def test_ics_falls_back_to_utc_for_daylight_saving_zones(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    event = await make_published_event(
        session, timezone="Europe/Berlin", starts_at=STARTS, ends_at=ENDS
    )
    await session.commit()

    lines = _unfold((await client.get(f"{API_PREFIX}/events/{event.slug}/calendar.ics")).text)

    assert "DTSTART:20261220T140000Z" in lines
    assert not any(line.startswith("BEGIN:VTIMEZONE") for line in lines)


async def test_cancelled_event_is_marked_cancelled(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    event = await make_published_event(
        session, status=EventStatus.CANCELLED, cancelled_at=datetime.now(UTC)
    )
    await session.commit()

    lines = _unfold((await client.get(f"{API_PREFIX}/events/{event.slug}/calendar.ics")).text)

    assert "STATUS:CANCELLED" in lines


async def test_ics_follows_event_visibility(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    organizer = await make_organizer(session)
    private = await make_published_event(session, organizer, visibility=EventVisibility.PRIVATE)
    draft = await make_published_event(session, organizer, status=EventStatus.DRAFT)
    stranger = await make_user(session)
    await session.commit()

    for headers in ({}, bearer(stranger)):
        r = await client.get(f"{API_PREFIX}/events/{private.slug}/calendar.ics", headers=headers)
        assert r.status_code == 404
    r = await client.get(f"{API_PREFIX}/events/{draft.slug}/calendar.ics")
    assert r.status_code == 404
    r = await client.get(
        f"{API_PREFIX}/events/{private.slug}/calendar.ics",
        headers=bearer(await session.get_one(User, organizer.user_id)),
    )
    assert r.status_code == 200


def test_fold_never_splits_a_character() -> None:
    line = "SUMMARY:" + "Қазақстан " * 20
    folded = _fold(line)
    parts = folded.split("\r\n")
    assert all(len(p.encode()) <= 75 for p in parts)
    assert "".join(p[1:] if i else p for i, p in enumerate(parts)) == line
