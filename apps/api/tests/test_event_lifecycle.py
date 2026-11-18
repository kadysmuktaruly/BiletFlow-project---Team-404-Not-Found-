"""SRS 4.2: publish, unpublish and cancel; visibility; registration window; capacity; preview."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, EventVisibility, OrderStatus, TicketStatus
from app.main import API_PREFIX
from app.models import AuditLogEntry, Event, Order, OrganizerProfile, Ticket, Venue
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_event,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
    organizer_bearer,
)

ORG = f"{API_PREFIX}/organizer/events"


async def _draft(
    session: AsyncSession, *, verified: bool = True, **event: Any
) -> tuple[OrganizerProfile, Event, dict[str, str]]:
    organizer = await make_organizer(session, is_email_verified=verified)
    venue = Venue(name="Hall", address_line1="Abay 1", city="Almaty", country_code="KZ")
    session.add(venue)
    await session.flush()
    ev = await make_event(session, organizer, venue_id=venue.id, **event)
    await session.commit()
    return organizer, ev, await organizer_bearer(session, organizer)


async def test_publish_needs_a_visible_ticket_type(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _draft(session)
    first = await client.post(f"{ORG}/{event.id}/publish", headers=headers)
    assert first.status_code == 409
    assert first.json()["error"]["code"] == "no_ticket_types"

    await make_ticket_type(session, event, is_hidden=True)
    await session.commit()
    assert (await client.post(f"{ORG}/{event.id}/publish", headers=headers)).status_code == 409

    await make_ticket_type(session, event)
    await session.commit()
    published = await client.post(f"{ORG}/{event.id}/publish", headers=headers)
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None
    actions = list(
        await session.scalars(
            select(AuditLogEntry.action_type).where(AuditLogEntry.event_id == event.id)
        )
    )
    assert "event.published" in actions


async def test_publish_needs_a_verified_email(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _draft(session, verified=False)
    await make_ticket_type(session, event)
    await session.commit()
    response = await client.post(f"{ORG}/{event.id}/publish", headers=headers)
    assert response.json()["error"]["code"] == "email_not_verified"


async def test_publish_rejects_past_events(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    past = datetime.now(UTC) - timedelta(days=2)
    _, event, headers = await _draft(session, starts_at=past, ends_at=past + timedelta(hours=2))
    await make_ticket_type(session, event)
    await session.commit()
    response = await client.post(f"{ORG}/{event.id}/publish", headers=headers)
    assert response.json()["error"]["code"] == "event_in_past"


async def test_unpublish_hides_page_and_stops_sales_but_keeps_tickets(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _draft(session)
    tt = await make_ticket_type(session, event)
    buyer = await make_user(session)
    await session.commit()
    await client.post(f"{ORG}/{event.id}/publish", headers=headers)
    order = (
        await client.post(
            f"{API_PREFIX}/orders",
            headers=bearer(buyer),
            json={
                "event_id": str(event.id),
                "items": [{"ticket_type_id": str(tt.id), "quantity": 1}],
            },
        )
    ).json()

    response = await client.post(f"{ORG}/{event.id}/unpublish", headers=headers)
    assert response.json()["status"] == "unpublished"
    assert (await client.get(f"{API_PREFIX}/events/{event.slug}")).status_code == 404
    blocked = await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={"event_id": str(event.id), "items": [{"ticket_type_id": str(tt.id), "quantity": 1}]},
    )
    assert blocked.json()["error"]["code"] == "event_not_on_sale"
    ticket = await session.get_one(Ticket, order["tickets"][0]["id"])
    assert ticket.status is TicketStatus.VALID

    # And it can be published again.
    assert (await client.post(f"{ORG}/{event.id}/publish", headers=headers)).json()[
        "status"
    ] == "published"


async def test_cancel_cancels_tickets_and_releases_unpaid_orders(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer)
    free = await make_ticket_type(session, event, price_kzt=0)
    paid = await make_ticket_type(session, event, price_kzt=5000, quantity_total=5)
    await enable_paid_sales(session, event)
    buyer = await make_user(session)
    await session.commit()
    headers = await organizer_bearer(session, organizer)

    def order_body(tt_id: object) -> dict[str, Any]:
        return {"event_id": str(event.id), "items": [{"ticket_type_id": str(tt_id), "quantity": 1}]}

    confirmed = (
        await client.post(f"{API_PREFIX}/orders", headers=bearer(buyer), json=order_body(free.id))
    ).json()
    pending = (
        await client.post(f"{API_PREFIX}/orders", headers=bearer(buyer), json=order_body(paid.id))
    ).json()

    response = await client.post(
        f"{ORG}/{event.id}/cancel", headers=headers, json={"reason": "Venue flooded"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    ticket = await session.get_one(Ticket, confirmed["tickets"][0]["id"])
    assert ticket.status is TicketStatus.CANCELLED
    pending_order = await session.get_one(Order, pending["id"])
    assert pending_order.status is OrderStatus.CANCELLED
    await session.refresh(paid)
    assert paid.quantity_reserved == 0
    # Cancelled events can't be edited or cancelled again.
    assert (
        await client.post(f"{ORG}/{event.id}/cancel", headers=headers, json={})
    ).status_code == 409
    assert (
        await client.patch(f"{ORG}/{event.id}", headers=headers, json={"title": "x"})
    ).status_code == 409


@pytest.mark.parametrize(
    ("from_status", "action"),
    [
        (EventStatus.DRAFT, "unpublish"),
        (EventStatus.PUBLISHED, "publish"),
        (EventStatus.CANCELLED, "publish"),
    ],
)
async def test_invalid_transitions(
    client: httpx.AsyncClient, session: AsyncSession, from_status: EventStatus, action: str
) -> None:
    _, event, headers = await _draft(session, status=from_status)
    await make_ticket_type(session, event)
    await session.commit()
    response = await client.post(f"{ORG}/{event.id}/{action}", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"


async def test_settings_visibility_window_capacity(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _draft(session)
    response = await client.patch(
        f"{ORG}/{event.id}",
        headers=headers,
        json={
            "visibility": "unlisted",
            "registration_opens_at": "2026-11-20T09:00",
            "registration_closes_at": "2026-12-19T23:00",
            "capacity": 150,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["visibility"] == "unlisted"
    assert body["capacity"] == 150
    assert body["registration_opens_at_local"] == "2026-11-20T09:00"
    assert datetime.fromisoformat(body["registration_opens_at"]) == datetime(
        2026, 11, 20, 4, tzinfo=UTC
    )

    bad_window = await client.patch(
        f"{ORG}/{event.id}",
        headers=headers,
        json={"registration_closes_at": "2026-11-01T09:00"},
    )
    assert bad_window.json()["error"]["code"] == "invalid_registration_window"

    cleared = await client.patch(f"{ORG}/{event.id}", headers=headers, json={"capacity": None})
    assert cleared.json()["capacity"] is None


async def test_capacity_cannot_drop_below_sold(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _draft(session)
    await make_ticket_type(session, event, quantity_total=50, quantity_sold=10)
    await session.commit()
    response = await client.patch(f"{ORG}/{event.id}", headers=headers, json={"capacity": 9})
    assert response.json()["error"]["code"] == "capacity_below_sold"
    assert (
        await client.patch(f"{ORG}/{event.id}", headers=headers, json={"capacity": 10})
    ).status_code == 200


async def test_registration_window_is_enforced_at_checkout(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    event = await make_published_event(session, registration_opens_at=now + timedelta(days=1))
    tt = await make_ticket_type(session, event)
    buyer = await make_user(session)
    await session.commit()
    body = {"event_id": str(event.id), "items": [{"ticket_type_id": str(tt.id), "quantity": 1}]}
    early = await client.post(f"{API_PREFIX}/orders", headers=bearer(buyer), json=body)
    assert early.json()["error"]["code"] == "registration_not_open"
    page = (await client.get(f"{API_PREFIX}/events/{event.slug}")).json()
    assert page["registration_open"] is False


async def test_preview_shows_a_draft_to_its_organizer_only(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _draft(session)
    await make_ticket_type(session, event, name="Early bird")
    stranger = await make_organizer(session)
    await session.commit()
    preview = await client.get(f"{ORG}/{event.id}/preview", headers=headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["preview"] is True
    assert body["status"] == "draft"
    assert [t["name"] for t in body["ticket_types"]] == ["Early bird"]
    assert (
        await client.get(
            f"{ORG}/{event.id}/preview", headers=await organizer_bearer(session, stranger)
        )
    ).status_code == 404
    assert (await client.get(f"{API_PREFIX}/events/{event.slug}")).status_code == 404


async def test_public_listing_and_visibility(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    public = await make_published_event(session, organizer, title="Public gig")
    unlisted = await make_published_event(
        session, organizer, title="Unlisted gig", visibility=EventVisibility.UNLISTED
    )
    private = await make_published_event(
        session, organizer, title="Private gig", visibility=EventVisibility.PRIVATE
    )
    await make_event(session, organizer, title="Draft gig")
    staff_user = await make_user(session)
    await session.commit()

    listing = (await client.get(f"{API_PREFIX}/events")).json()
    assert [e["title"] for e in listing["items"]] == ["Public gig"]
    assert listing["total"] == 1
    assert (await client.get(f"{API_PREFIX}/events", params={"q": "nothing"})).json()["total"] == 0

    assert (await client.get(f"{API_PREFIX}/events/{public.slug}")).status_code == 200
    assert (await client.get(f"{API_PREFIX}/events/{unlisted.slug}")).status_code == 200
    assert (await client.get(f"{API_PREFIX}/events/{private.slug}")).status_code == 404

    owner_headers = await organizer_bearer(session, organizer)
    assert (
        await client.get(f"{API_PREFIX}/events/{private.slug}", headers=owner_headers)
    ).status_code == 200
    await client.post(
        f"{ORG}/{private.id}/staff", headers=owner_headers, json={"email": staff_user.email}
    )
    staff_view = await client.get(f"{API_PREFIX}/events/{private.slug}", headers=bearer(staff_user))
    assert staff_view.status_code == 200
