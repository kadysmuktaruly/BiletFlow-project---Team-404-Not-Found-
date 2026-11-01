"""SRS 4.4 / 4.6 / 4.7: orders reserve stock, free orders issue tickets at once, paid orders
wait for payment, and abandoned reservations return to sale."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, EventVisibility, OrderStatus
from app.main import API_PREFIX
from app.models import Event, Order, Ticket, TicketType, User
from app.services.orders import sweep_expired
from app.tickets.tokens import parse_admission_token
from tests.factories import bearer, make_published_event, make_ticket_type, make_user

ORDERS = f"{API_PREFIX}/orders"


def _order(event: Event, *lines: tuple[TicketType, int], **extra: Any) -> dict[str, Any]:
    return {
        "event_id": str(event.id),
        "items": [{"ticket_type_id": str(tt.id), "quantity": q} for tt, q in lines],
        **extra,
    }


async def _buyer(session: AsyncSession, **kw: Any) -> User:
    return await make_user(session, full_name="Aigerim Nurlanqyzy", **kw)


async def test_free_order_zero_total_issues_tickets(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    free = await make_ticket_type(session, event, price_kzt=0, quantity_total=50)
    buyer = await _buyer(session)
    await session.commit()

    response = await client.post(
        ORDERS,
        headers=bearer(buyer),
        json=_order(
            event,
            (free, 2),
            attendees=[
                {"full_name": "Aigerim N"},
                {"full_name": "Daniyar K", "email": "d@example.com"},
            ],
        ),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["total_kzt"] == body["subtotal_kzt"] == 0
    assert body["payment_required"] is False
    assert body["reference"].startswith("BF-")
    assert [t["attendee_name"] for t in body["tickets"]] == ["Aigerim N", "Daniyar K"]
    assert "processing_fee_kzt" not in body  # attendees see only the ticket price

    numbers = {t["ticket_number"] for t in body["tickets"]}
    assert len(numbers) == 2
    for ticket in body["tickets"]:
        assert ticket["status"] == "valid"
        assert str(parse_admission_token(ticket["qr_payload"])) == ticket["id"]

    await session.refresh(free)
    assert (free.quantity_sold, free.quantity_reserved) == (2, 0)


async def test_paid_order_has_no_tickets_until_paid(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    paid = await make_ticket_type(session, event, price_kzt=7500, quantity_total=10)
    buyer = await _buyer(session)
    await session.commit()

    before = datetime.now(UTC)
    response = await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (paid, 2)))
    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "awaiting_payment"
    assert body["payment_required"] is True
    assert body["subtotal_kzt"] == body["total_kzt"] == 15000
    assert body["tickets"] == []
    expires = datetime.fromisoformat(body["expires_at"])
    assert timedelta(seconds=590) < expires - before < timedelta(seconds=610)

    await session.refresh(paid)
    assert (paid.quantity_sold, paid.quantity_reserved) == (0, 2)
    assert await session.scalar(select(func.count()).select_from(Ticket)) == 0


async def test_client_cannot_set_prices_or_totals(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    paid = await make_ticket_type(session, event, price_kzt=7500)
    buyer = await _buyer(session)
    await session.commit()
    response = await client.post(
        ORDERS,
        headers=bearer(buyer),
        json={
            **_order(event, (paid, 1)),
            "total_kzt": 1,
            "discount_kzt": 7499,
            "items": [{"ticket_type_id": str(paid.id), "quantity": 1, "unit_price_kzt": 1}],
        },
    )
    assert response.json()["total_kzt"] == 7500


async def test_expired_reservation_releases_stock(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    last = await make_ticket_type(session, event, price_kzt=5000, quantity_total=1)
    first, second = await _buyer(session), await _buyer(session)
    await session.commit()

    held = await client.post(ORDERS, headers=bearer(first), json=_order(event, (last, 1)))
    assert held.status_code == 201
    blocked = await client.post(ORDERS, headers=bearer(second), json=_order(event, (last, 1)))
    assert blocked.json()["error"]["code"] == "sold_out"

    # The first buyer walks away; their reservation runs out.
    order = await session.get_one(Order, held.json()["id"])
    order.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    # No sweep has run, yet the next checkout for this event releases it first.
    retry = await client.post(ORDERS, headers=bearer(second), json=_order(event, (last, 1)))
    assert retry.status_code == 201
    await session.refresh(order)
    assert order.status is OrderStatus.EXPIRED
    await session.refresh(last)
    assert (last.quantity_sold, last.quantity_reserved) == (0, 1)


async def test_background_sweep_expires_orders(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    tt = await make_ticket_type(session, event, price_kzt=5000, quantity_total=5)
    buyer = await _buyer(session)
    await session.commit()
    created = await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (tt, 3)))
    order = await session.get_one(Order, created.json()["id"])
    order.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.commit()

    assert await sweep_expired(session) == 1
    await session.commit()
    await session.refresh(tt)
    assert tt.quantity_reserved == 0
    assert await sweep_expired(session) == 0  # idempotent


async def test_per_order_limit(client: httpx.AsyncClient, session: AsyncSession) -> None:
    event = await make_published_event(session)
    tt = await make_ticket_type(session, event, max_per_order=2)
    buyer = await _buyer(session)
    await session.commit()
    response = await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (tt, 3)))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "max_per_order_exceeded"


@pytest.mark.parametrize(
    ("window", "code"),
    [
        ({"sales_start_at": timedelta(days=1)}, "sales_not_started"),
        ({"sales_end_at": timedelta(days=-1)}, "sales_ended"),
    ],
)
async def test_sales_window(
    client: httpx.AsyncClient, session: AsyncSession, window: dict[str, timedelta], code: str
) -> None:
    event = await make_published_event(session)
    now = datetime.now(UTC)
    tt = await make_ticket_type(session, event, **{k: now + v for k, v in window.items()})
    buyer = await _buyer(session)
    await session.commit()
    response = await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (tt, 1)))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code


async def test_hidden_ticket_type_cannot_be_ordered(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    tt = await make_ticket_type(session, event, is_hidden=True)
    buyer = await _buyer(session)
    await session.commit()
    response = await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (tt, 1)))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ticket_type_not_found"


@pytest.mark.parametrize(
    ("event_overrides", "status", "code"),
    [
        ({"status": EventStatus.DRAFT}, 404, "event_not_found"),
        ({"visibility": EventVisibility.PRIVATE}, 404, "event_not_found"),
        ({"status": EventStatus.UNPUBLISHED}, 409, "event_not_on_sale"),
        ({"status": EventStatus.CANCELLED}, 409, "event_not_on_sale"),
        ({"is_suspended": True}, 409, "sales_suspended"),
        ({"registration_opens_at": timedelta(days=1)}, 409, "registration_not_open"),
        ({"registration_closes_at": timedelta(days=-1)}, 409, "registration_closed"),
    ],
)
async def test_event_must_be_open_for_registration(
    client: httpx.AsyncClient,
    session: AsyncSession,
    event_overrides: dict[str, Any],
    status: int,
    code: str,
) -> None:
    now = datetime.now(UTC)
    overrides = {k: now + v if isinstance(v, timedelta) else v for k, v in event_overrides.items()}
    event = await make_published_event(session, None, **overrides)
    tt = await make_ticket_type(session, event)
    buyer = await _buyer(session)
    await session.commit()
    response = await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (tt, 1)))
    assert (response.status_code, response.json()["error"]["code"]) == (status, code)


async def test_attendee_count_must_match(client: httpx.AsyncClient, session: AsyncSession) -> None:
    event = await make_published_event(session)
    tt = await make_ticket_type(session, event)
    buyer = await _buyer(session)
    await session.commit()
    response = await client.post(
        ORDERS,
        headers=bearer(buyer),
        json=_order(event, (tt, 2), attendees=[{"full_name": "Only one"}]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "attendee_count_mismatch"

    defaulted = await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (tt, 2)))
    assert [t["attendee_name"] for t in defaulted.json()["tickets"]] == [buyer.full_name] * 2


async def test_checkout_requires_sign_in(client: httpx.AsyncClient, session: AsyncSession) -> None:
    event = await make_published_event(session)
    tt = await make_ticket_type(session, event)
    await session.commit()
    response = await client.post(ORDERS, json=_order(event, (tt, 1)))
    assert response.status_code == 401


async def test_orders_and_tickets_are_private_to_the_buyer(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    tt = await make_ticket_type(session, event)
    buyer, other = await _buyer(session), await _buyer(session)
    await session.commit()
    order = (await client.post(ORDERS, headers=bearer(buyer), json=_order(event, (tt, 1)))).json()
    ticket_id = order["tickets"][0]["id"]

    assert (await client.get(f"{ORDERS}/{order['id']}", headers=bearer(buyer))).status_code == 200
    assert (await client.get(f"{ORDERS}/{order['id']}", headers=bearer(other))).status_code == 404

    mine = await client.get(f"{API_PREFIX}/me/tickets", headers=bearer(buyer))
    assert [t["id"] for t in mine.json()] == [ticket_id]
    assert mine.json()[0]["event"]["title"] == event.title
    assert (await client.get(f"{API_PREFIX}/me/tickets", headers=bearer(other))).json() == []

    qr = await client.get(f"{API_PREFIX}/me/tickets/{ticket_id}/qr.svg", headers=bearer(buyer))
    assert qr.status_code == 200
    assert qr.headers["content-type"].startswith("image/svg+xml")
    assert qr.text.lstrip().startswith("<svg")
    denied = await client.get(f"{API_PREFIX}/me/tickets/{ticket_id}/qr.svg", headers=bearer(other))
    assert denied.status_code == 404

    history = await client.get(f"{API_PREFIX}/me/orders", headers=bearer(buyer))
    assert [o["id"] for o in history.json()] == [order["id"]]
