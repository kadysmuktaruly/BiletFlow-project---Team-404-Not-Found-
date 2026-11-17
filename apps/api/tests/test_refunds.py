"""SRS 4.9 orders, cancellations and refunds (DEMO): full idempotent refunds, cancelling free
registrations, refunded or cancelled tickets failing at the door, automatic refunds when an
event is cancelled, audit entries, notifications, and the organizer's order list."""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NotificationChannel, PaymentStatus, StaffRole, TicketStatus
from app.main import API_PREFIX
from app.models import (
    AuditLogEntry,
    Event,
    Notification,
    Payment,
    Refund,
    StaffAssignment,
    Ticket,
    TicketType,
    User,
)
from app.services.mail import OutgoingEmail
from app.services.order_emails import format_kzt
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)


@dataclass
class Box:
    event: Event
    owner: User
    paid: TicketType  # 8,000 KZT
    free: TicketType

    def url(self, path: str = "") -> str:
        return f"{API_PREFIX}/organizer/events/{self.event.id}{path}"


async def make_box(session: AsyncSession) -> Box:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer, title="Almaty Jazz Night")
    paid = await make_ticket_type(
        session, event, name="Standard", price_kzt=8000, quantity_total=50
    )
    free = await make_ticket_type(session, event, name="Student", price_kzt=0, quantity_total=50)
    await enable_paid_sales(session, event)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    await session.commit()
    return Box(event=event, owner=owner, paid=paid, free=free)


async def order(
    client: httpx.AsyncClient, box: Box, buyer: User, tt: TicketType, n: int = 1
) -> dict[str, Any]:
    response = await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={
            "event_id": str(box.event.id),
            "items": [{"ticket_type_id": str(tt.id), "quantity": n}],
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def paid_order(
    client: httpx.AsyncClient, box: Box, buyer: User, n: int = 1
) -> dict[str, Any]:
    placed = await order(client, box, buyer, box.paid, n)
    paid = await client.post(
        f"{API_PREFIX}/orders/{placed['id']}/payments",
        headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "succeed"},
    )
    assert paid.status_code == 201, paid.text
    body: dict[str, Any] = paid.json()["order"]
    return body


async def refund(
    client: httpx.AsyncClient,
    box: Box,
    order_id: str,
    key: str | None = None,
    user: User | None = None,
) -> httpx.Response:
    return await client.post(
        box.url(f"/orders/{order_id}/refund"),
        headers={**bearer(user or box.owner), "Idempotency-Key": key or str(uuid.uuid4())},
        json={"reason": "Customer asked"},
    )


async def sold(session: AsyncSession, tt: TicketType) -> int:
    await session.refresh(tt)
    return tt.quantity_sold


# --- refunds --------------------------------------------------------------------------------


async def test_full_refund_invalidates_tickets_returns_stock_audits_and_notifies(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    box = await make_box(session)
    buyer = await make_user(session, locale="en")
    await session.commit()
    placed = await paid_order(client, box, buyer, n=2)
    assert await sold(session, box.paid) == 2
    mail.clear()

    response = await refund(client, box, placed["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["replayed"] is False
    assert (body["refund"]["amount_kzt"], body["refund"]["status"], body["refund"]["demo"]) == (
        16000,
        "succeeded",
        True,
    )
    assert body["refund"]["is_simulated"] is True
    assert (body["order"]["status"], body["order"]["refunded_kzt"]) == ("refunded", 16000)
    assert (body["order"]["can_refund"], body["order"]["can_cancel"]) == (False, False)

    statuses = set(
        await session.scalars(
            select(Ticket.status).where(Ticket.order_id == uuid.UUID(placed["id"]))
        )
    )
    assert statuses == {TicketStatus.REFUNDED}
    assert await sold(session, box.paid) == 0  # back on sale
    payment = await session.scalar(
        select(Payment).where(Payment.order_id == uuid.UUID(placed["id"]))
    )
    assert payment is not None
    await session.refresh(payment)
    assert payment.status is PaymentStatus.REFUNDED

    # SRS 4.9: refunded tickets fail at the door.
    scan = await client.post(
        f"{API_PREFIX}/checkin/events/{box.event.id}/scan",
        headers=bearer(box.owner),
        json={"payload": placed["tickets"][0]["qr_payload"]},
    )
    assert scan.json()["result"] == "refunded"

    entry = await session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action_type == "order.refunded")
    )
    assert entry is not None
    assert entry.actor_user_id == box.owner.id and "DEMO" in entry.description
    assert [m.template for m in mail] == ["refund_completed"]
    assert format_kzt(16000) in mail[0].text and "DEMO" in mail[0].subject
    in_app = await session.scalar(
        select(Notification).where(
            Notification.user_id == buyer.id,
            Notification.channel == NotificationChannel.IN_APP,
            Notification.action_path == f"/orders/{placed['id']}",
        )
    )
    assert in_app is not None
    # The attendee sees the refund on their order.
    mine = (await client.get(f"{API_PREFIX}/orders/{placed['id']}", headers=bearer(buyer))).json()
    assert (mine["status"], mine["refunded_kzt"]) == ("refunded", 16000)


async def test_refund_is_idempotent(client: httpx.AsyncClient, session: AsyncSession) -> None:
    box = await make_box(session)
    buyer, other = await make_user(session), await make_user(session)
    await session.commit()
    first_order = await paid_order(client, box, buyer)
    second_order = await paid_order(client, box, other)

    key = "refund-attempt-0001"
    first = await refund(client, box, first_order["id"], key)
    again = await refund(client, box, first_order["id"], key)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["replayed"] is True
    assert again.json()["refund"]["id"] == first.json()["refund"]["id"]

    new_key = await refund(client, box, first_order["id"])
    assert (new_key.status_code, new_key.json()["error"]["code"]) == (409, "order_already_refunded")
    reused = await refund(client, box, second_order["id"], key)
    assert (reused.status_code, reused.json()["error"]["code"]) == (409, "idempotency_key_reused")
    assert await session.scalar(select(func.count()).select_from(Refund)) == 1


async def test_concurrent_refund_requests_refund_once(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    box = await make_box(session)
    buyer = await make_user(session)
    await session.commit()
    placed = await paid_order(client, box, buyer)

    same_key = await asyncio.gather(
        *(refund(client, box, placed["id"], "double-click-key") for _ in range(6))
    )
    assert sorted(r.status_code for r in same_key) == [200] * 5 + [201]
    assert len({r.json()["refund"]["id"] for r in same_key}) == 1

    other = await paid_order(client, box, buyer)
    new_keys = await asyncio.gather(*(refund(client, box, other["id"]) for _ in range(6)))
    assert sorted(r.status_code for r in new_keys) == [201] + [409] * 5
    assert await session.scalar(select(func.count()).select_from(Refund)) == 2


async def test_free_and_unpaid_orders_cannot_be_refunded(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    box = await make_box(session)
    buyer = await make_user(session)
    await session.commit()
    free = await order(client, box, buyer, box.free)
    unpaid = await order(client, box, buyer, box.paid)
    for o in (free, unpaid):
        response = await refund(client, box, o["id"])
        assert (response.status_code, response.json()["error"]["code"]) == (
            409,
            "order_not_refundable",
        )
    missing = await refund(client, box, str(uuid.uuid4()))
    assert missing.status_code == 404


# --- free registrations ---------------------------------------------------------------------


async def test_cancel_free_registration(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    box = await make_box(session)
    buyer = await make_user(session, locale="en")
    await session.commit()
    free = await order(client, box, buyer, box.free, n=2)
    paid = await paid_order(client, box, buyer)
    assert await sold(session, box.free) == 2
    mail.clear()

    url = box.url(f"/orders/{free['id']}/cancel")
    response = await client.post(
        url, headers=bearer(box.owner), json={"reason": "Duplicate sign-up"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    statuses = set(
        await session.scalars(select(Ticket.status).where(Ticket.order_id == uuid.UUID(free["id"])))
    )
    assert statuses == {TicketStatus.CANCELLED}
    assert await sold(session, box.free) == 0
    assert [m.template for m in mail] == ["registration_cancelled"]
    entry = await session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action_type == "order.registration_cancelled")
    )
    assert entry is not None and "Duplicate sign-up" in entry.description
    scan = await client.post(
        f"{API_PREFIX}/checkin/events/{box.event.id}/scan",
        headers=bearer(box.owner),
        json={"payload": free["tickets"][0]["qr_payload"]},
    )
    assert scan.json()["result"] == "cancelled"

    again = await client.post(url, headers=bearer(box.owner), json={})
    assert (again.status_code, again.json()["error"]["code"]) == (409, "order_not_cancellable")
    paid_cancel = await client.post(
        box.url(f"/orders/{paid['id']}/cancel"), headers=bearer(box.owner), json={}
    )
    assert (paid_cancel.status_code, paid_cancel.json()["error"]["code"]) == (
        409,
        "order_not_cancellable",
    )


# --- who may act ----------------------------------------------------------------------------


async def test_only_the_event_owner_refunds_or_cancels(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    box = await make_box(session)
    other_box = await make_box(session)
    buyer = await make_user(session)
    event_admin = await make_user(session)
    session.add(
        StaffAssignment(
            event_id=box.event.id,
            user_id=event_admin.id,
            role=StaffRole.EVENT_ADMIN,
            assigned_by_user_id=box.owner.id,
        )
    )
    await session.commit()
    placed = await paid_order(client, box, buyer)
    free = await order(client, box, buyer, box.free)

    assert (await refund(client, box, placed["id"], user=other_box.owner)).status_code == 404
    for outsider in (buyer, event_admin):
        assert (await refund(client, box, placed["id"], user=outsider)).status_code == 403
        assert (await client.get(box.url("/orders"), headers=bearer(outsider))).status_code == 403
    cancel = await client.post(
        box.url(f"/orders/{free['id']}/cancel"), headers=bearer(other_box.owner), json={}
    )
    assert cancel.status_code == 404
    # Another event's order is not found through this event.
    cross = await client.post(
        other_box.url(f"/orders/{placed['id']}/refund"),
        headers={**bearer(other_box.owner), "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert cross.status_code == 404
    assert await session.scalar(select(func.count()).select_from(Refund)) == 0


# --- cancelling an event --------------------------------------------------------------------


async def test_cancelling_an_event_refunds_every_paid_order(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    box = await make_box(session)
    a, b, c, d = [await make_user(session, locale="en") for _ in range(4)]
    await session.commit()
    paid_a = await paid_order(client, box, a, n=2)
    paid_b = await paid_order(client, box, b)
    free_c = await order(client, box, c, box.free)
    pending_d = await order(client, box, d, box.paid)
    mail.clear()

    response = await client.post(
        box.url("/cancel"), headers=bearer(box.owner), json={"reason": "Venue flooded"}
    )
    assert response.status_code == 200, response.text

    refunds = list(await session.scalars(select(Refund)))
    assert sorted(r.amount_kzt for r in refunds) == [8000, 16000]
    for placed in (paid_a, paid_b):
        mine = (
            await client.get(
                f"{API_PREFIX}/orders/{placed['id']}", headers=bearer(a if placed is paid_a else b)
            )
        ).json()
        assert (mine["status"], mine["refunded_kzt"]) == ("refunded", mine["total_kzt"])
        assert {t["status"] for t in mine["tickets"]} == {"refunded"}
    free_tickets = (
        await client.get(f"{API_PREFIX}/orders/{free_c['id']}", headers=bearer(c))
    ).json()["tickets"]
    assert {t["status"] for t in free_tickets} == {"cancelled"}
    pending = (await client.get(f"{API_PREFIX}/orders/{pending_d['id']}", headers=bearer(d))).json()
    assert pending["status"] == "cancelled"

    by_person: dict[str, list[str]] = {}
    for m in mail:
        by_person.setdefault(m.to, []).append(m.template)
    assert sorted(by_person[a.email]) == ["event_cancelled", "refund_completed"]
    assert sorted(by_person[b.email]) == ["event_cancelled", "refund_completed"]
    assert by_person[c.email] == ["event_cancelled"]
    assert d.email not in by_person  # never paid, never held a ticket
    actions = list(
        await session.scalars(
            select(AuditLogEntry.action_type).where(AuditLogEntry.event_id == box.event.id)
        )
    )
    assert actions.count("order.refunded") == 2 and "event.cancelled" in actions

    # Cancelling again does nothing (and refunds nothing twice).
    again = await client.post(box.url("/cancel"), headers=bearer(box.owner), json={})
    assert again.status_code == 409
    assert await session.scalar(select(func.count()).select_from(Refund)) == 2


# --- the organizer's order list and refund policy ------------------------------------------


async def test_order_list_search_status_and_actions(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    box = await make_box(session)
    alice = await make_user(session, full_name="Alice Paid")
    bob = await make_user(session, full_name="Bob Free")
    await session.commit()
    paid = await paid_order(client, box, alice)
    free = await order(client, box, bob, box.free)

    listed = (await client.get(box.url("/orders"), headers=bearer(box.owner))).json()
    rows = {o["reference"]: o for o in listed["orders"]}
    assert (rows[paid["reference"]]["can_refund"], rows[paid["reference"]]["can_cancel"]) == (
        True,
        False,
    )
    assert (rows[free["reference"]]["can_refund"], rows[free["reference"]]["can_cancel"]) == (
        False,
        True,
    )
    assert rows[paid["reference"]]["buyer_name"] == "Alice Paid"
    assert rows[paid["reference"]]["tickets"] == 1

    by_name = (
        await client.get(box.url("/orders"), headers=bearer(box.owner), params={"q": "bob"})
    ).json()
    assert [o["reference"] for o in by_name["orders"]] == [free["reference"]]
    by_ref = (
        await client.get(
            box.url("/orders"), headers=bearer(box.owner), params={"q": paid["reference"].lower()}
        )
    ).json()
    assert [o["reference"] for o in by_ref["orders"]] == [paid["reference"]]
    await refund(client, box, paid["id"])
    refunded = (
        await client.get(
            box.url("/orders"), headers=bearer(box.owner), params={"status": "refunded"}
        )
    ).json()
    assert [o["reference"] for o in refunded["orders"]] == [paid["reference"]]


async def test_refund_policy_is_set_by_the_organizer_and_shown_publicly(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    box = await make_box(session)
    policy = "Full refunds until 48 hours before the event."
    response = await client.patch(
        box.url(), headers=bearer(box.owner), json={"refund_policy": policy}
    )
    assert response.status_code == 200 and response.json()["refund_policy"] == policy
    public = (await client.get(f"{API_PREFIX}/events/{box.event.slug}")).json()
    assert public["refund_policy"] == policy
