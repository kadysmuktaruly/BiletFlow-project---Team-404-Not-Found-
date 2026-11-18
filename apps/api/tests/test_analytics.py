"""SRS 4.15 basic organizer analytics: capacity, sales, revenue (gross, discounts, refunds,
net, fees), sales over time and by ticket type, campaigns, attendance; filters; own events
only; and it never gets in checkout's way (SRS 7)."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import API_PREFIX
from app.models import Event, TicketType, User
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)

URL = f"{API_PREFIX}/organizer/analytics"


@dataclass
class Venue:
    event: Event
    owner: User
    standard: TicketType  # 10,000 KZT x 50
    vip: TicketType  # 25,000 KZT x 20


async def make_venue(session: AsyncSession) -> Venue:
    organizer = await make_organizer(session)
    ev = await make_published_event(session, organizer, title="Jazz", timezone="Asia/Almaty")
    standard = await make_ticket_type(
        session, ev, name="Standard", price_kzt=10_000, quantity_total=50
    )
    vip = await make_ticket_type(session, ev, name="VIP", price_kzt=25_000, quantity_total=20)
    await enable_paid_sales(session, ev)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    await session.commit()
    return Venue(ev, owner, standard, vip)


async def buy(
    client: httpx.AsyncClient,
    buyer: User,
    v: Venue,
    tt: TicketType,
    n: int,
    *,
    pay: bool = True,
    code: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event_id": str(v.event.id),
        "items": [{"ticket_type_id": str(tt.id), "quantity": n}],
    }
    if code:
        body["promo_code"] = code
    placed = await client.post(f"{API_PREFIX}/orders", headers=bearer(buyer), json=body)
    assert placed.status_code == 201, placed.text
    order: dict[str, Any] = placed.json()
    if pay:
        paid = await client.post(
            f"{API_PREFIX}/orders/{order['id']}/payments",
            headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
            json={"outcome": "succeed"},
        )
        assert paid.status_code == 201, paid.text
        order = paid.json()["order"]
    return order


async def analytics(client: httpx.AsyncClient, user: User, **params: Any) -> dict[str, Any]:
    response = await client.get(URL, headers=bearer(user), params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def scenario(client: httpx.AsyncClient, session: AsyncSession) -> Venue:
    """Two Standard with a 10% code, one VIP, one Standard refunded, one VIP unpaid, and one
    ticket checked in."""
    v = await make_venue(session)
    a, b, c, d = [await make_user(session) for _ in range(4)]
    await session.commit()
    await client.post(
        f"{API_PREFIX}/organizer/events/{v.event.id}/campaigns",
        headers=bearer(v.owner),
        json={
            "name": "Autumn",
            "discount_type": "percentage",
            "discount_percent": 10,
            "code": "TEN",
        },
    )
    promo = await buy(client, a, v, v.standard, 2, code="TEN")
    await buy(client, b, v, v.vip, 1)
    refunded = await buy(client, c, v, v.standard, 1)
    await buy(client, d, v, v.vip, 1, pay=False)
    response = await client.post(
        f"{API_PREFIX}/organizer/events/{v.event.id}/orders/{refunded['id']}/refund",
        headers={**bearer(v.owner), "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert response.status_code == 201
    scan = await client.post(
        f"{API_PREFIX}/checkin/events/{v.event.id}/scan",
        headers=bearer(v.owner),
        json={"payload": promo["tickets"][0]["qr_payload"]},
    )
    assert scan.json()["result"] == "valid"
    return v


async def test_figures_for_one_event(client: httpx.AsyncClient, session: AsyncSession) -> None:
    v = await scenario(client, session)
    body = await analytics(client, v.owner, event_id=str(v.event.id))

    assert body["capacity"] == {"capacity": 70, "sold": 3, "remaining": 67, "percent_sold": 4.3}
    assert body["revenue"] == {
        "tickets_sold": 3,
        "tickets_refunded": 1,
        "gross_kzt": 55_000,  # 2 x 10,000 + 25,000 + 10,000 (refunded)
        "discounts_kzt": 2_000,
        "refunds_kzt": 10_000,
        "net_kzt": 43_000,
        "processing_fees_kzt": 1_290,  # 3% of 18,000 and of 25,000
        "estimated_payout_kzt": 41_710,
        "demo": True,
    }
    assert body["attendance"] == {
        "issued": 3,
        "checked_in": 1,
        "absent": 2,
        "percent_checked_in": 33.3,
    }
    types = {t["name"]: t for t in body["by_ticket_type"]}
    assert (types["Standard"]["tickets_in_range"], types["Standard"]["revenue_kzt"]) == (2, 18_000)
    assert (types["VIP"]["tickets_in_range"], types["VIP"]["revenue_kzt"]) == (1, 25_000)
    assert types["Standard"]["checked_in"] == 1
    (campaign,) = body["campaigns"]
    assert {
        k: campaign[k]
        for k in (
            "code",
            "redemptions",
            "orders",
            "tickets",
            "gross_kzt",
            "discount_kzt",
            "net_kzt",
        )
    } == {
        "code": "TEN",
        "redemptions": 1,
        "orders": 1,
        "tickets": 2,
        "gross_kzt": 20_000,
        "discount_kzt": 2_000,
        "net_kzt": 18_000,
    }
    # Sales over time: the default is the last 30 days in the event's zone, one point a day.
    points = body["sales_over_time"]
    today = datetime.now(ZoneInfo("Asia/Almaty")).date()
    assert len(points) == 30 and points[-1]["date"] == today.isoformat()
    assert (points[-1]["tickets"], points[-1]["revenue_kzt"]) == (3, 43_000)
    assert sum(p["tickets"] for p in points) == 3
    assert body["filters"]["timezone"] == "Asia/Almaty"


async def test_ticket_type_and_date_filters(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    v = await scenario(client, session)
    vip = await analytics(client, v.owner, event_id=str(v.event.id), ticket_type_id=str(v.vip.id))
    assert (vip["revenue"]["tickets_sold"], vip["revenue"]["gross_kzt"]) == (1, 25_000)
    assert vip["capacity"]["capacity"] == 20
    assert [t["name"] for t in vip["by_ticket_type"]] == ["VIP"]
    assert vip["campaigns"][0]["tickets"] == 0  # the code was used on Standard tickets

    tomorrow = date.today() + timedelta(days=2)
    future = await analytics(
        client,
        v.owner,
        date_from=tomorrow.isoformat(),
        date_to=(tomorrow + timedelta(days=6)).isoformat(),
    )
    assert future["revenue"]["tickets_sold"] == 0 and len(future["sales_over_time"]) == 7
    assert future["capacity"]["sold"] == 3  # capacity is the current state, not the range

    for params in (
        {"date_from": "2026-12-10", "date_to": "2026-12-01"},
        {"date_from": "2025-01-01", "date_to": "2026-12-31"},
    ):
        response = await client.get(URL, headers=bearer(v.owner), params=params)
        assert (response.status_code, response.json()["error"]["code"]) == (
            422,
            "invalid_date_range",
        )


async def test_only_your_own_events(client: httpx.AsyncClient, session: AsyncSession) -> None:
    mine = await scenario(client, session)
    theirs = await make_venue(session)
    stranger = await make_user(session)
    await session.commit()
    await buy(client, stranger, theirs, theirs.vip, 2)

    everything = await analytics(client, mine.owner)
    assert everything["revenue"]["gross_kzt"] == 55_000  # their 50,000 isn't here
    assert {t["event_id"] for t in everything["by_ticket_type"]} == {str(mine.event.id)}
    foreign = await client.get(
        URL, headers=bearer(mine.owner), params={"event_id": str(theirs.event.id)}
    )
    assert foreign.status_code == 404
    foreign_type = await client.get(
        URL, headers=bearer(mine.owner), params={"ticket_type_id": str(theirs.vip.id)}
    )
    assert foreign_type.status_code == 404
    assert (await client.get(URL, headers=bearer(stranger))).status_code == 403
    assert (await client.get(URL)).status_code == 401


async def test_analytics_never_holds_up_checkout(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """SRS 7: analytics "shall not block or delay ticket selection, checkout, payment
    confirmation, or ticket issuance". Run dashboards and checkouts at the same moment."""
    v = await make_venue(session)
    buyers = [await make_user(session) for _ in range(8)]
    await session.commit()

    async def checkout(user: User) -> httpx.Response:
        return await client.post(
            f"{API_PREFIX}/orders",
            headers=bearer(user),
            json={
                "event_id": str(v.event.id),
                "items": [{"ticket_type_id": str(v.standard.id), "quantity": 1}],
            },
        )

    started = asyncio.get_running_loop().time()
    results = await asyncio.gather(
        *(client.get(URL, headers=bearer(v.owner)) for _ in range(8)),
        *(checkout(b) for b in buyers),
    )
    elapsed = asyncio.get_running_loop().time() - started
    assert [r.status_code for r in results[:8]] == [200] * 8
    assert [r.status_code for r in results[8:]] == [201] * 8
    assert elapsed < 10
