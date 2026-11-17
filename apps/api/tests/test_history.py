"""SRS 4.16 event history: Upcoming / Active / Completed / Cancelled views, past events
read-only, the activity timeline (filters, same permissions as the records), and
duplicating an event without its transactions."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, StaffRole, UserRole
from app.main import API_PREFIX
from app.models import (
    Event,
    Order,
    PaidSalesActivation,
    PromotionalCampaign,
    StaffAssignment,
    Ticket,
    TicketType,
    User,
    Venue,
)
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)

ORG = f"{API_PREFIX}/organizer"


async def owner_of(session: AsyncSession) -> tuple[Any, User]:
    organizer = await make_organizer(session)
    user = await session.get(User, organizer.user_id)
    assert user is not None
    return organizer, user


async def test_events_are_grouped_by_phase(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer, owner = await owner_of(session)
    now = datetime.now(UTC)
    upcoming = await make_published_event(session, organizer, title="Next month")
    active = await make_published_event(
        session,
        organizer,
        title="On now",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
    )
    ended = await make_published_event(
        session,
        organizer,
        title="Last week",
        starts_at=now - timedelta(days=7),
        ends_at=now - timedelta(days=7, hours=-3),
    )
    cancelled = await make_published_event(
        session, organizer, title="Called off", status=EventStatus.CANCELLED
    )
    draft = await make_published_event(session, organizer, title="Draft", status=EventStatus.DRAFT)
    await session.commit()

    everything = (await client.get(f"{ORG}/events", headers=bearer(owner))).json()
    assert {e["title"]: e["phase"] for e in everything} == {
        "Next month": "upcoming",
        "On now": "active",
        "Last week": "completed",
        "Called off": "cancelled",
        "Draft": "upcoming",
    }
    for phase, expected in (
        ("upcoming", {upcoming.title, draft.title}),
        ("active", {active.title}),
        ("completed", {ended.title}),
        ("cancelled", {cancelled.title}),
    ):
        listed = (
            await client.get(f"{ORG}/events", headers=bearer(owner), params={"phase": phase})
        ).json()
        assert {e["title"] for e in listed} == expected, phase
    assert (
        await client.get(f"{ORG}/events", headers=bearer(owner), params={"phase": "later"})
    ).status_code == 422


async def test_past_events_are_read_only_but_keep_their_records(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer, owner = await owner_of(session)
    event = await make_published_event(session, organizer)
    tt = await make_ticket_type(session, event, price_kzt=5000)
    await enable_paid_sales(session, event)
    buyer = await make_user(session)
    await session.commit()
    placed = (
        await client.post(
            f"{API_PREFIX}/orders",
            headers=bearer(buyer),
            json={
                "event_id": str(event.id),
                "items": [{"ticket_type_id": str(tt.id), "quantity": 1}],
            },
        )
    ).json()
    await client.post(
        f"{API_PREFIX}/orders/{placed['id']}/payments",
        headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "succeed"},
    )
    # The event ends.
    past = datetime.now(UTC) - timedelta(days=1)
    await session.execute(
        update(Event)
        .where(Event.id == event.id)
        .values(starts_at=past - timedelta(hours=3), ends_at=past)
    )
    await session.commit()
    url = f"{ORG}/events/{event.id}"

    for method, path, body in (
        ("PATCH", "", {"title": "Renamed"}),
        ("POST", "/ticket-types", {"name": "Late", "price_kzt": 0, "quantity_total": 5}),
        ("PATCH", f"/ticket-types/{tt.id}", {"price_kzt": 1}),
        ("POST", "/campaigns", {"name": "x", "discount_type": "percentage", "discount_percent": 5}),
    ):
        response = await client.request(method, f"{url}{path}", headers=bearer(owner), json=body)
        assert (response.status_code, response.json()["error"]["code"]) == (
            409,
            "event_not_editable",
        ), path
    assert (await client.post(f"{url}/cancel", headers=bearer(owner), json={})).status_code == 409
    # Its records stay open to review, and a refund is still possible.
    assert len((await client.get(f"{url}/orders", headers=bearer(owner))).json()["orders"]) == 1
    assert (await client.get(f"{url}/attendees", headers=bearer(owner))).status_code == 200
    refund = await client.post(
        f"{url}/orders/{placed['id']}/refund",
        headers={**bearer(owner), "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert refund.status_code == 201


async def test_timeline_shows_the_events_story(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer, owner = await owner_of(session)
    venue = Venue(name="Hall", address_line1="Abay 1", city="Almaty")
    session.add(venue)
    await session.flush()
    event = await make_published_event(
        session, organizer, status=EventStatus.DRAFT, title="Meetup", venue_id=venue.id
    )
    tt = await make_ticket_type(session, event)
    event_admin = await make_user(session, full_name="Ella Admin")
    scanner, stranger = await make_user(session), await make_user(session)
    admin = await make_user(session, role=UserRole.PLATFORM_ADMIN)
    for user, role in ((event_admin, StaffRole.EVENT_ADMIN), (scanner, StaffRole.CHECK_IN_STAFF)):
        session.add(
            StaffAssignment(
                event_id=event.id, user_id=user.id, role=role, assigned_by_user_id=owner.id
            )
        )
    owner.is_email_verified = True
    await session.commit()
    url = f"{ORG}/events/{event.id}"
    assert (await client.post(f"{url}/publish", headers=bearer(owner))).status_code == 200
    await client.patch(
        f"{url}/ticket-types/{tt.id}", headers=bearer(owner), json={"quantity_total": 150}
    )
    await client.post(
        f"{url}/campaigns",
        headers=bearer(owner),
        json={"name": "Early", "discount_type": "percentage", "discount_percent": 5},
    )
    order = (
        await client.post(
            f"{API_PREFIX}/orders",
            headers=bearer(stranger),
            json={
                "event_id": str(event.id),
                "items": [{"ticket_type_id": str(tt.id), "quantity": 1}],
            },
        )
    ).json()
    ticket = order["tickets"][0]
    scan_url = f"{API_PREFIX}/checkin/events/{event.id}"
    await client.post(
        f"{scan_url}/scan", headers=bearer(event_admin), json={"payload": ticket["qr_payload"]}
    )
    await client.post(
        f"{scan_url}/tickets/{ticket['id']}/undo", headers=bearer(event_admin), json={}
    )

    timeline_url = f"{API_PREFIX}/history/events/{event.id}/timeline"
    body = (await client.get(timeline_url, headers=bearer(owner))).json()
    actions = [e["action"] for e in body["entries"]]
    assert actions[:2] == ["ticket.check_in_reversed", "ticket.checked_in"]  # newest first
    for expected in ("event.published", "ticket_type.quantity_changed", "promo.created"):
        assert any(a == expected or a.startswith(expected.split(".")[0] + ".") for a in actions), (
            expected
        )
    reversal = body["entries"][0]
    assert (
        reversal["actor_name"] == "Ella Admin"
        and reversal["category"] == "ticket"
        and reversal["description"]
    )
    assert {"event", "promo", "ticket"} <= set(body["categories"])

    promos = (
        await client.get(timeline_url, headers=bearer(owner), params={"category": "promo"})
    ).json()
    assert {e["category"] for e in promos["entries"]} == {"promo"}
    tomorrow = (datetime.now(ZoneInfo(event.timezone)) + timedelta(days=1)).date().isoformat()
    later = (
        await client.get(timeline_url, headers=bearer(owner), params={"date_from": tomorrow})
    ).json()
    assert later["entries"] == []

    # Same permissions as the records: owner, event admins and platform admins only.
    for user, code in ((event_admin, 200), (admin, 200), (scanner, 404), (stranger, 404)):
        assert (await client.get(timeline_url, headers=bearer(user))).status_code == code
    _, other_owner = await owner_of(session)
    await session.commit()
    assert (await client.get(timeline_url, headers=bearer(other_owner))).status_code == 404


async def test_duplicate_copies_configuration_but_no_transactions(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer, owner = await owner_of(session)
    zone = ZoneInfo("Asia/Almaty")
    start = datetime(2026, 10, 2, 19, 0, tzinfo=zone)  # a Friday, in the past
    source = await make_published_event(
        session,
        organizer,
        title="Jazz Night",
        starts_at=start,
        ends_at=start + timedelta(hours=3),
        capacity=80,
        refund_policy="Refunds until 48 hours before.",
        timezone="Asia/Almaty",
    )
    paid = await make_ticket_type(
        session, source, name="Standard", price_kzt=8000, quantity_total=60
    )
    await make_ticket_type(
        session, source, name="Student", price_kzt=0, quantity_total=20, is_hidden=True
    )
    await enable_paid_sales(session, source)
    session.add(
        PromotionalCampaign(
            event_id=source.id,
            name="Old",
            discount_type="percentage",
            discount_percent=5,
            qr_token="BFC1.old-campaign",
            created_by_user_id=owner.id,
        )
    )
    await session.execute(
        update(TicketType).where(TicketType.id == paid.id).values(quantity_sold=12)
    )
    await session.commit()

    response = await client.post(f"{ORG}/events/{source.id}/duplicate", headers=bearer(owner))
    assert response.status_code == 201, response.text
    copy = response.json()
    assert (copy["title"], copy["status"], copy["phase"]) == ("Jazz Night", "draft", "upcoming")
    assert copy["slug"] != source.slug and copy["id"] != str(source.id)
    assert (copy["capacity"], copy["refund_policy"]) == (80, "Refunds until 48 hours before.")
    starts = datetime.fromisoformat(copy["starts_at"]).astimezone(zone)
    assert starts > datetime.now(UTC)
    assert (starts.weekday(), starts.hour, starts.minute) == (
        4,
        19,
        0,
    )  # same local weekday and time
    assert copy["ends_at_local"].endswith("22:00")

    copy_id = uuid.UUID(copy["id"])
    types = list(
        await session.scalars(
            select(TicketType).where(TicketType.event_id == copy_id).order_by(TicketType.name)
        )
    )
    assert [
        (t.name, t.price_kzt, t.quantity_total, t.quantity_sold, t.is_hidden) for t in types
    ] == [
        ("Standard", 8000, 60, 0, False),
        ("Student", 0, 20, 0, True),
    ]
    for model in (Order, Ticket, PromotionalCampaign, PaidSalesActivation):
        count = await session.scalar(
            select(func.count()).select_from(model).where(model.event_id == copy_id)
        )
        assert count == 0, model.__name__
    stored = await session.get(Event, copy_id)
    assert stored is not None and stored.duplicated_from_event_id == source.id
    if source.venue_id:
        assert stored.venue_id != source.venue_id  # its own venue row, editable separately

    _, stranger = await owner_of(session)
    await session.commit()
    assert (
        await client.post(f"{ORG}/events/{source.id}/duplicate", headers=bearer(stranger))
    ).status_code == 404
    history = (
        await client.get(f"{API_PREFIX}/history/events/{source.id}/timeline", headers=bearer(owner))
    ).json()
    assert history["entries"][0]["action"] == "event.duplicated"
