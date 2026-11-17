"""SRS 4.14 promo codes and Campaign QR codes: server-side discounts, case-insensitive codes,
validity dates, the redemption limit under concurrency, eligible ticket types, clear
rejection reasons, campaign link resolution and per-campaign reporting."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import DiscountType, EventVisibility
from app.main import API_PREFIX
from app.models import AuditLogEntry, Event, PromoCode, PromoRedemption, TicketType, User
from app.schemas.promo import CampaignCreate
from app.services import promotions
from app.tickets.tokens import parse_admission_token
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)

ORDERS = f"{API_PREFIX}/orders"


@dataclass
class Shop:
    event: Event
    owner: User
    standard: TicketType  # 10,000 KZT
    vip: TicketType  # 25,000 KZT
    free: TicketType

    @property
    def campaigns(self) -> str:
        return f"{API_PREFIX}/organizer/events/{self.event.id}/campaigns"


async def make_shop(session: AsyncSession, **event: Any) -> Shop:
    organizer = await make_organizer(session)
    ev = await make_published_event(session, organizer, **event)
    standard = await make_ticket_type(session, ev, name="Standard", price_kzt=10_000)
    vip = await make_ticket_type(session, ev, name="VIP", price_kzt=25_000)
    free = await make_ticket_type(session, ev, name="Student", price_kzt=0)
    await enable_paid_sales(session, ev)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    await session.commit()
    return Shop(event=ev, owner=owner, standard=standard, vip=vip, free=free)


async def create_campaign(client: httpx.AsyncClient, shop: Shop, **body: Any) -> dict[str, Any]:
    body.setdefault("name", "Autumn launch")
    body.setdefault("discount_type", "percentage")
    if body["discount_type"] == "percentage":
        body.setdefault("discount_percent", 20)
    for key in ("ticket_type_ids",):
        if key in body:
            body[key] = [str(v) for v in body[key]]
    for key in ("starts_at", "ends_at"):
        if isinstance(body.get(key), datetime):
            body[key] = body[key].isoformat()
    response = await client.post(shop.campaigns, headers=bearer(shop.owner), json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def items(*lines: tuple[TicketType, int]) -> list[dict[str, Any]]:
    return [{"ticket_type_id": str(tt.id), "quantity": q} for tt, q in lines]


async def order(
    client: httpx.AsyncClient,
    shop: Shop,
    buyer: User,
    lines: list[dict[str, Any]],
    code: str | None = None,
    **extra: Any,
) -> httpx.Response:
    body: dict[str, Any] = {"event_id": str(shop.event.id), "items": lines, **extra}
    if code is not None:
        body["promo_code"] = code
    return await client.post(ORDERS, headers=bearer(buyer), json=body)


async def quote(
    client: httpx.AsyncClient, shop: Shop, code: str, lines: list[dict[str, Any]]
) -> httpx.Response:
    return await client.post(
        f"{API_PREFIX}/promo/validate",
        json={"event_id": str(shop.event.id), "code": code, "items": lines},
    )


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


# --- creating campaigns -------------------------------------------------------------------


async def test_create_campaign_generates_code_and_opaque_campaign_link(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    created = await create_campaign(client, shop)
    assert created["status"] == "active"
    assert len(created["code"]) == 8
    assert created["redeemed_count"] == 0
    assert created["ticket_type_ids"] == []
    # The QR link carries only an opaque token: no price, no discount (SRS 4.14).
    token = created["qr_token"]
    assert token.startswith("BFC1.")
    assert created["campaign_url"].endswith(f"/c/{token}")
    assert "discount" not in created["campaign_url"]
    # Disjoint from admission tokens: it can never be read as a ticket.
    assert parse_admission_token(token) is None
    assert parse_admission_token(created["campaign_url"]) is None
    entry = await session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action_type == "promo.created")
    )
    assert entry is not None
    assert entry.event_id == shop.event.id


async def test_codes_are_case_insensitive_and_unique(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    other = await make_shop(session)
    await create_campaign(client, shop, code="Summer20")
    clash = await client.post(
        other.campaigns,
        headers=bearer(other.owner),
        json={
            "name": "x",
            "discount_type": "percentage",
            "discount_percent": 5,
            "code": "SUMMER20",
        },
    )
    assert (clash.status_code, error_code(clash)) == (409, "promo_code_taken")

    buyer = await make_user(session)
    await session.commit()
    for spelling in ("summer20", "SUMMER20", " SuMmEr20 "):
        response = await quote(client, shop, spelling, items((shop.standard, 1)))
        assert response.status_code == 200, response.text
        assert response.json()["code"] == "Summer20"
    placed = await order(client, shop, buyer, items((shop.standard, 1)), code="sUmMeR20")
    assert placed.status_code == 201
    assert placed.json()["promo_code"] == "Summer20"


async def test_campaign_validation_and_ownership(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    stranger_shop = await make_shop(session)
    bad_bodies = [
        {"name": "x", "discount_type": "percentage"},
        {"name": "x", "discount_type": "percentage", "discount_percent": 0},
        {"name": "x", "discount_type": "percentage", "discount_percent": 101},
        {"name": "x", "discount_type": "fixed_kzt"},
        {"name": "x", "discount_type": "fixed_kzt", "discount_kzt": 500, "discount_percent": 5},
        {"name": "x", "discount_type": "percentage", "discount_percent": 5, "code": "a b"},
        {
            "name": "x",
            "discount_type": "percentage",
            "discount_percent": 5,
            "starts_at": "2026-12-02T00:00:00Z",
            "ends_at": "2026-12-01T00:00:00Z",
        },
    ]
    for body in bad_bodies:
        response = await client.post(shop.campaigns, headers=bearer(shop.owner), json=body)
        assert response.status_code == 422, body
    foreign_type = await client.post(
        shop.campaigns,
        headers=bearer(shop.owner),
        json={
            "name": "x",
            "discount_type": "percentage",
            "discount_percent": 5,
            "ticket_type_ids": [str(stranger_shop.standard.id)],
        },
    )
    assert foreign_type.status_code == 404
    # Another organizer can't see or create campaigns on this event.
    for method in ("GET", "POST"):
        response = await client.request(
            method,
            shop.campaigns,
            headers=bearer(stranger_shop.owner),
            json={"name": "x", "discount_type": "percentage", "discount_percent": 5},
        )
        assert response.status_code == 404
    attendee = await make_user(session)
    await session.commit()
    assert (await client.get(shop.campaigns, headers=bearer(attendee))).status_code == 403


# --- discounts, computed on the server ----------------------------------------------------


async def test_percentage_discount_applied_server_side_and_recorded(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    campaign = await create_campaign(client, shop, code="AUTUMN15", discount_percent=15)
    buyer = await make_user(session)
    await session.commit()

    lines = items((shop.standard, 2), (shop.vip, 1))  # 20,000 + 25,000
    preview = (await quote(client, shop, "autumn15", lines)).json()
    assert (preview["subtotal_kzt"], preview["discount_kzt"], preview["total_kzt"]) == (
        45_000,
        6_750,
        38_250,
    )

    # Whatever the client claims about money is ignored (SRS 4.14, SRS 7).
    placed = await order(
        client,
        shop,
        buyer,
        lines,
        code="autumn15",
        discount_kzt=45_000,
        total_kzt=1,
        subtotal_kzt=1,
    )
    assert placed.status_code == 201, placed.text
    body = placed.json()
    assert (body["subtotal_kzt"], body["discount_kzt"], body["total_kzt"]) == (
        45_000,
        6_750,
        38_250,
    )
    assert body["campaign_name"] == "Autumn launch"
    assert [(i["discount_kzt"], i["line_total_kzt"]) for i in body["items"]] == [
        (3_000, 17_000),
        (3_750, 21_250),
    ]
    # The redemption is held while payment is pending, and recorded once it succeeds.
    assert (
        await client.get(f"{shop.campaigns}/{campaign['id']}", headers=bearer(shop.owner))
    ).json()["redeemed_count"] == 1
    assert await session.scalar(select(func.count()).select_from(PromoRedemption)) == 0
    paid = await client.post(
        f"{ORDERS}/{body['id']}/payments",
        headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "succeed"},
    )
    assert paid.status_code == 201, paid.text
    redemption = await session.scalar(select(PromoRedemption))
    assert redemption is not None
    assert (redemption.discount_kzt, redemption.order_total_kzt) == (6_750, 38_250)

    report = (
        await client.get(f"{shop.campaigns}/{campaign['id']}", headers=bearer(shop.owner))
    ).json()["report"]
    assert report == {
        "redemptions": 1,
        "orders": 1,
        "tickets_sold": 3,
        "gross_revenue_kzt": 45_000,
        "discount_kzt": 6_750,
        "net_revenue_kzt": 38_250,
    }


async def test_fixed_discount_is_capped_split_and_limited_to_eligible_types(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    await create_campaign(
        client,
        shop,
        code="VIP5000",
        discount_type="fixed_kzt",
        discount_kzt=5_000,
        ticket_type_ids=[shop.vip.id],
    )
    await create_campaign(
        client, shop, code="BIG", discount_type="fixed_kzt", discount_kzt=1_000_000
    )
    await create_campaign(client, shop, code="SPLIT", discount_type="fixed_kzt", discount_kzt=1_001)

    vip_only = (
        await quote(client, shop, "vip5000", items((shop.standard, 1), (shop.vip, 2)))
    ).json()
    assert [line["discount_kzt"] for line in vip_only["lines"]] == [0, 5_000]
    assert vip_only["total_kzt"] == 10_000 + 50_000 - 5_000

    capped = (await quote(client, shop, "big", items((shop.standard, 1)))).json()
    assert (capped["discount_kzt"], capped["total_kzt"]) == (10_000, 0)

    split = (await quote(client, shop, "split", items((shop.standard, 1), (shop.vip, 1)))).json()
    assert sum(line["discount_kzt"] for line in split["lines"]) == 1_001
    assert [line["discount_kzt"] for line in split["lines"]] == [286, 715]


async def test_full_discount_on_a_paid_ticket_confirms_at_once(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    await create_campaign(client, shop, code="ONTHEHOUSE", discount_percent=100)
    buyer = await make_user(session)
    await session.commit()
    placed = await order(client, shop, buyer, items((shop.standard, 1)), code="onthehouse")
    assert placed.status_code == 201
    body = placed.json()
    assert (body["status"], body["total_kzt"], len(body["tickets"])) == ("confirmed", 0, 1)
    assert await session.scalar(select(func.count()).select_from(PromoRedemption)) == 1


# --- rejections ---------------------------------------------------------------------------


async def test_rejections_give_a_clear_reason(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    other = await make_shop(session)
    now = datetime.now(UTC)
    await create_campaign(
        client, shop, code="OLD", ends_at=now - timedelta(days=1), starts_at=now - timedelta(days=9)
    )
    await create_campaign(client, shop, code="SOON", starts_at=now + timedelta(days=3))
    off = await create_campaign(client, shop, code="OFF")
    await create_campaign(client, shop, code="ONCE", max_redemptions=1)
    await create_campaign(client, shop, code="VIPONLY", ticket_type_ids=[shop.vip.id])
    await create_campaign(client, other, code="ELSEWHERE")
    disabled = await client.post(
        f"{shop.campaigns}/{off['id']}/disable", headers=bearer(shop.owner)
    )
    assert disabled.json()["status"] == "disabled"
    first, second = await make_user(session), await make_user(session)
    await session.commit()
    assert (
        await order(client, shop, first, items((shop.standard, 1)), code="ONCE")
    ).status_code == 201

    expected = {
        "OLD": (409, "promo_expired"),
        "SOON": (409, "promo_not_started"),
        "OFF": (409, "promo_disabled"),
        "ONCE": (409, "promo_exhausted"),
        "VIPONLY": (409, "promo_not_applicable"),
        "ELSEWHERE": (404, "promo_not_found"),
        "NOSUCHCODE": (404, "promo_not_found"),
    }
    for code, (status, reason) in expected.items():
        previewed = await quote(client, shop, code, items((shop.standard, 1)))
        assert (previewed.status_code, error_code(previewed)) == (status, reason), code
        placed = await order(client, shop, second, items((shop.standard, 1)), code=code)
        assert (placed.status_code, error_code(placed)) == (status, reason), code
    # A rejected code holds nothing back: the stock and the buyer are free to try again.
    assert (await order(client, shop, second, items((shop.standard, 1)))).status_code == 201
    # Free tickets have nothing to discount.
    free_only = await quote(client, shop, "VIPONLY", items((shop.free, 1)))
    assert error_code(free_only) == "promo_not_applicable"


# --- the redemption limit -----------------------------------------------------------------


async def test_promo_limit_holds_under_concurrency(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    campaign = await create_campaign(client, shop, code="FIRST3", max_redemptions=3)
    buyers = [await make_user(session) for _ in range(10)]
    await session.commit()

    responses = await asyncio.gather(
        *(order(client, shop, b, items((shop.standard, 1)), code="first3") for b in buyers)
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201] * 3 + [409] * 7, statuses
    assert {error_code(r) for r in responses if r.status_code == 409} == {"promo_exhausted"}
    code = await session.scalar(select(PromoCode).where(PromoCode.code == "FIRST3"))
    assert code is not None
    await session.refresh(code)
    assert code.redeemed_count == 3
    read = (
        await client.get(f"{shop.campaigns}/{campaign['id']}", headers=bearer(shop.owner))
    ).json()
    assert read["status"] == "exhausted"


async def test_database_rejects_redemptions_past_the_limit(session: AsyncSession) -> None:
    """`ck_promo_codes_within_limit` is the backstop, whatever the application does."""
    shop = await make_shop(session)
    campaign = await promotions.create(
        session,
        shop.event,
        shop.owner,
        CampaignCreate(
            name="x",
            discount_type=DiscountType.PERCENTAGE,
            discount_percent=5,
            max_redemptions=1,
            code="LIMIT1",
        ),
    )
    await session.execute(
        text("UPDATE promo_codes SET redeemed_count = 1 WHERE campaign_id = :c"), {"c": campaign.id}
    )
    await session.commit()
    with pytest.raises(IntegrityError, match="ck_promo_codes_within_limit"):
        await session.execute(
            text(
                "UPDATE promo_codes SET redeemed_count = redeemed_count + 1 WHERE campaign_id = :c"
            ),
            {"c": campaign.id},
        )
    await session.rollback()


async def test_abandoned_or_failed_orders_give_the_redemption_back(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    await create_campaign(client, shop, code="ONLYONE", max_redemptions=1)
    first, second = await make_user(session), await make_user(session)
    await session.commit()

    held = await order(client, shop, first, items((shop.standard, 1)), code="ONLYONE")
    assert held.status_code == 201
    blocked = await order(client, shop, second, items((shop.standard, 1)), code="ONLYONE")
    assert error_code(blocked) == "promo_exhausted"

    await client.post(f"{ORDERS}/{held.json()['id']}/abandon", headers=bearer(first))
    retry = await order(client, shop, second, items((shop.standard, 1)), code="ONLYONE")
    assert retry.status_code == 201, retry.text

    failed = await client.post(
        f"{ORDERS}/{retry.json()['id']}/payments",
        headers={**bearer(second), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "fail"},
    )
    assert failed.status_code == 201
    again = await order(client, shop, first, items((shop.standard, 1)), code="ONLYONE")
    assert again.status_code == 201
    assert await session.scalar(select(func.count()).select_from(PromoRedemption)) == 0


# --- managing campaigns -------------------------------------------------------------------


async def test_update_limits_and_dates_and_disable(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    campaign = await create_campaign(client, shop, code="TWEAK", max_redemptions=5)
    buyers = [await make_user(session) for _ in range(2)]
    await session.commit()
    for b in buyers:
        await order(client, shop, b, items((shop.standard, 1)), code="TWEAK")
    url = f"{shop.campaigns}/{campaign['id']}"

    too_low = await client.patch(url, headers=bearer(shop.owner), json={"max_redemptions": 1})
    assert (too_low.status_code, error_code(too_low)) == (409, "max_redemptions_below_used")
    changed = await client.patch(
        url, headers=bearer(shop.owner), json={"name": "Renamed", "max_redemptions": 2}
    )
    assert changed.status_code == 200
    assert (changed.json()["name"], changed.json()["status"]) == ("Renamed", "exhausted")
    unlimited = await client.patch(url, headers=bearer(shop.owner), json={"max_redemptions": None})
    assert unlimited.json()["status"] == "active"

    disabled = await client.post(f"{url}/disable", headers=bearer(shop.owner))
    assert disabled.json()["status"] == "disabled"
    assert disabled.json()["disabled_at"] is not None
    actions = set(
        await session.scalars(
            select(AuditLogEntry.action_type).where(
                AuditLogEntry.entity_id == uuid.UUID(campaign["id"])
            )
        )
    )
    assert {"promo.created", "promo.updated", "promo.disabled"} <= actions
    listed = (await client.get(shop.campaigns, headers=bearer(shop.owner))).json()
    assert [c["id"] for c in listed] == [campaign["id"]]


# --- Campaign QR links --------------------------------------------------------------------


async def test_campaign_token_resolves_event_and_code(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session)
    live = await create_campaign(client, shop, code="QRCODE10", discount_percent=10)
    off = await create_campaign(client, shop, code="QROFF")
    await client.post(f"{shop.campaigns}/{off['id']}/disable", headers=bearer(shop.owner))

    resolved = await client.get(f"{API_PREFIX}/campaigns/resolve/{live['qr_token']}")
    assert resolved.status_code == 200
    assert resolved.json() == {
        "event_id": str(shop.event.id),
        "event_slug": shop.event.slug,
        "code": "QRCODE10",
        "campaign_name": "Autumn launch",
        "rejection": None,
    }
    rejected = (await client.get(f"{API_PREFIX}/campaigns/resolve/{off['qr_token']}")).json()
    assert (rejected["code"], rejected["rejection"], rejected["event_slug"]) == (
        None,
        "promo_disabled",
        shop.event.slug,
    )
    unknown = await client.get(f"{API_PREFIX}/campaigns/resolve/BFC1.doesnotexist")
    assert (unknown.status_code, error_code(unknown)) == (404, "campaign_not_found")
    # An admission token is not a campaign token either.
    assert (await client.get(f"{API_PREFIX}/campaigns/resolve/BFT1.abc.def")).status_code == 404


async def test_private_event_campaign_links_stay_private(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    shop = await make_shop(session, visibility=EventVisibility.PRIVATE)
    hidden = await create_campaign(client, shop, code="SECRET")
    outsider = await client.get(f"{API_PREFIX}/campaigns/resolve/{hidden['qr_token']}")
    assert outsider.status_code == 404
    owner = await client.get(
        f"{API_PREFIX}/campaigns/resolve/{hidden['qr_token']}", headers=bearer(shop.owner)
    )
    assert owner.status_code == 200
