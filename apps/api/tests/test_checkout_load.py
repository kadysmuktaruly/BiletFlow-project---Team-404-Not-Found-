"""SRS 7: "The checkout process should remain usable under temporary increases in event
traffic." A simple spike test (SRS compliance check NFR-7): 50 attendees check out at the same
moment for the last 10 paid tickets, then the 10 winners all pay at once.

Every request is a separate signed-in user sent with asyncio.gather, so Postgres sees real
concurrent transactions competing for the app's connection pool. Pass means: exactly 10
tickets are sold, everyone else gets a clean 409 `sold_out`, and no request fails with a 5xx.
"""

import asyncio
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrderStatus, TicketStatus
from app.main import API_PREFIX
from app.models import Order, Ticket, TicketType
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_published_event,
    make_ticket_type,
    make_user,
)

BUYERS = 50
LAST_TICKETS = 10


async def test_fifty_concurrent_checkouts_for_the_last_ten_tickets(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    tickets = await make_ticket_type(
        session, event, quantity_total=LAST_TICKETS, price_kzt=8000, max_per_order=1
    )
    await enable_paid_sales(session, event)
    buyers = [await make_user(session) for _ in range(BUYERS)]
    await session.commit()

    async def checkout(headers: dict[str, str]) -> httpx.Response:
        return await client.post(
            f"{API_PREFIX}/orders",
            headers=headers,
            json={
                "event_id": str(event.id),
                "items": [{"ticket_type_id": str(tickets.id), "quantity": 1}],
            },
        )

    loop = asyncio.get_running_loop()
    started = loop.time()
    responses = await asyncio.gather(*(checkout(bearer(b)) for b in buyers))
    elapsed = loop.time() - started

    statuses = [r.status_code for r in responses]
    assert not [s for s in statuses if s >= 500], statuses
    assert statuses.count(201) == LAST_TICKETS, statuses
    assert statuses.count(409) == BUYERS - LAST_TICKETS, statuses
    assert {r.json()["error"]["code"] for r in responses if r.status_code == 409} == {"sold_out"}
    # "Usable": the whole spike is answered in seconds, not left hanging on locks.
    assert elapsed < 15, f"{BUYERS} checkouts took {elapsed:.1f}s"

    # The 10 winners pay at the same moment (DEMO payment), each with its own key.
    winners = [
        (b, r.json()) for b, r in zip(buyers, responses, strict=True) if r.status_code == 201
    ]
    payments = await asyncio.gather(
        *(
            client.post(
                f"{API_PREFIX}/orders/{order['id']}/payments",
                headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
                json={"outcome": "succeed"},
            )
            for buyer, order in winners
        )
    )
    assert [p.status_code for p in payments] == [201] * LAST_TICKETS, [p.text for p in payments]

    # Exactly 10 sold, 10 confirmed orders, 10 valid tickets; nothing oversold or left reserved.
    await session.refresh(tickets)
    assert (tickets.quantity_sold, tickets.quantity_reserved) == (LAST_TICKETS, 0)
    confirmed = await session.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.event_id == event.id, Order.status == OrderStatus.CONFIRMED)
    )
    assert confirmed == LAST_TICKETS
    valid = await session.scalar(
        select(func.count())
        .select_from(Ticket)
        .join(TicketType, TicketType.id == Ticket.ticket_type_id)
        .where(TicketType.id == tickets.id, Ticket.status == TicketStatus.VALID)
    )
    assert valid == LAST_TICKETS
