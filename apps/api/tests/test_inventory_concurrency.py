"""SRS 4.3 / 4.6: inventory is never oversold, even under concurrent checkout.

Written before the order service (Report 3 watch-out: "Write the concurrency test before
building the checkout screens"). Each request is a separate user with its own pooled
connection, sent at once with asyncio.gather, so Postgres sees truly concurrent transactions.
"""

import asyncio

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import API_PREFIX
from app.models import Order, Ticket, TicketType
from tests.factories import bearer, make_published_event, make_ticket_type, make_user

CONCURRENT_BUYERS = 10


@pytest.mark.parametrize("price_kzt", [0, 5000], ids=["free", "paid"])
async def test_last_ticket_sold_once_under_concurrency(
    client: httpx.AsyncClient, session: AsyncSession, price_kzt: int
) -> None:
    event = await make_published_event(session)
    last = await make_ticket_type(session, event, quantity_total=1, price_kzt=price_kzt)
    buyers = [await make_user(session) for _ in range(CONCURRENT_BUYERS)]
    await session.commit()

    async def buy(headers: dict[str, str]) -> httpx.Response:
        return await client.post(
            f"{API_PREFIX}/orders",
            headers=headers,
            json={
                "event_id": str(event.id),
                "items": [{"ticket_type_id": str(last.id), "quantity": 1}],
                "attendees": [{"full_name": "Buyer"}],
            },
        )

    responses = await asyncio.gather(*(buy(bearer(b)) for b in buyers))

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201] + [409] * (CONCURRENT_BUYERS - 1), statuses
    assert {r.json()["error"]["code"] for r in responses if r.status_code == 409} == {"sold_out"}

    await session.refresh(last)
    assert last.quantity_sold + last.quantity_reserved == 1
    assert await session.scalar(select(func.count()).select_from(Order)) == 1
    expected_tickets = 1 if price_kzt == 0 else 0  # paid tickets wait for payment
    assert await session.scalar(select(func.count()).select_from(Ticket)) == expected_tickets


async def test_capacity_holds_across_ticket_types_under_concurrency(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session, capacity=3)
    types = [await make_ticket_type(session, event, quantity_total=10) for _ in range(3)]
    buyers = [await make_user(session) for _ in range(9)]
    await session.commit()

    async def buy(i: int) -> httpx.Response:
        return await client.post(
            f"{API_PREFIX}/orders",
            headers=bearer(buyers[i]),
            json={
                "event_id": str(event.id),
                "items": [{"ticket_type_id": str(types[i % 3].id), "quantity": 1}],
                "attendees": [{"full_name": "Buyer"}],
            },
        )

    responses = await asyncio.gather(*(buy(i) for i in range(9)))
    assert sum(r.status_code == 201 for r in responses) == 3
    sold = await session.scalar(select(func.sum(TicketType.quantity_sold)))
    assert sold == 3
