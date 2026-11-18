"""SRS 4.6: the DEMO payment simulation succeeds, fails or is abandoned; retries are safe."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivationStatus,
    NotificationStatus,
    NotificationType,
    OrderStatus,
    PaymentStatus,
)
from app.main import API_PREFIX
from app.models import (
    Event,
    Notification,
    Order,
    PaidSalesActivation,
    Payment,
    Ticket,
    TicketType,
    User,
)
from app.services.mail import OutgoingEmail
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_published_event,
    make_ticket_type,
    make_user,
)

ORDERS = f"{API_PREFIX}/orders"


async def _paid_setup(
    session: AsyncSession, quantity_total: int = 10, price: int = 7500
) -> tuple[Event, TicketType, User]:
    event = await make_published_event(session, title="Almaty Jazz Night")
    tt = await make_ticket_type(session, event, price_kzt=price, quantity_total=quantity_total)
    await enable_paid_sales(session, event)
    buyer = await make_user(session, full_name="Aigerim N", locale="en")
    await session.commit()
    return event, tt, buyer


async def _reserve(
    client: httpx.AsyncClient, buyer: User, event: Event, tt: TicketType, qty: int = 2
) -> dict[str, object]:
    response = await client.post(
        ORDERS,
        headers=bearer(buyer),
        json={
            "event_id": str(event.id),
            "items": [{"ticket_type_id": str(tt.id), "quantity": qty}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


async def _pay(
    client: httpx.AsyncClient, buyer: User, order_id: object, outcome: str, key: str
) -> httpx.Response:
    return await client.post(
        f"{ORDERS}/{order_id}/payments",
        headers={**bearer(buyer), "Idempotency-Key": key},
        json={"outcome": outcome},
    )


async def test_successful_payment_issues_tickets_and_emails_qr(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, buyer = await _paid_setup(session)
    order = await _reserve(client, buyer, event, tt)

    response = await _pay(client, buyer, order["id"], "succeed", f"pay-{uuid.uuid4()}")
    assert response.status_code == 201
    body = response.json()
    assert body["replayed"] is False
    payment = body["payment"]
    assert payment["status"] == "succeeded"
    assert payment["demo"] is True and payment["is_simulated"] is True
    assert payment["provider"] == "simulated"
    assert payment["amount_kzt"] == 15000
    assert body["order"]["status"] == "confirmed"
    assert len(body["order"]["tickets"]) == 2

    await session.refresh(tt)
    assert (tt.quantity_sold, tt.quantity_reserved) == (2, 0)

    assert len(mail) == 1
    email = mail[0]
    assert email.to == buyer.email
    assert email.template == "order_confirmed"
    assert "Almaty Jazz Night" in email.subject
    assert "DEMO payment" in email.text
    qr_images = [a for a in email.attachments if a.mime_type == "image/png" and a.inline_cid]
    assert len(qr_images) == 2
    for ticket in body["order"]["tickets"]:
        assert ticket["ticket_number"] in email.text
        assert any(ticket["ticket_number"] in a.filename for a in qr_images)
    notification = await session.scalar(
        select(Notification).where(Notification.order_id == order["id"])
    )
    assert notification is not None
    assert notification.type is NotificationType.REGISTRATION_CONFIRMATION
    assert notification.status is NotificationStatus.SENT


async def test_payment_idempotent_retry(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, buyer = await _paid_setup(session)
    order = await _reserve(client, buyer, event, tt)
    key = f"retry-{uuid.uuid4()}"

    first = await _pay(client, buyer, order["id"], "succeed", key)
    again = await _pay(client, buyer, order["id"], "succeed", key)
    # A retry can't change the outcome either.
    flipped = await _pay(client, buyer, order["id"], "fail", key)

    assert first.status_code == 201
    assert again.status_code == flipped.status_code == 200
    assert again.json()["replayed"] is True
    assert again.json()["payment"]["id"] == first.json()["payment"]["id"]
    assert flipped.json()["payment"]["status"] == "succeeded"
    assert await session.scalar(select(func.count()).select_from(Payment)) == 1
    assert await session.scalar(select(func.count()).select_from(Ticket)) == 2
    assert len(mail) == 1


async def test_concurrent_retries_with_one_key_charge_once(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, buyer = await _paid_setup(session)
    order = await _reserve(client, buyer, event, tt)
    key = f"double-click-{uuid.uuid4()}"

    responses = await asyncio.gather(
        *(_pay(client, buyer, order["id"], "succeed", key) for _ in range(5))
    )
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 200, 201]
    assert len({r.json()["payment"]["id"] for r in responses}) == 1
    assert await session.scalar(select(func.count()).select_from(Payment)) == 1
    assert await session.scalar(select(func.count()).select_from(Ticket)) == 2
    assert len(mail) == 1


async def test_idempotency_key_reuse_conflict(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer = await _paid_setup(session)
    first = await _reserve(client, buyer, event, tt, qty=1)
    second = await _reserve(client, buyer, event, tt, qty=1)
    key = f"reused-{uuid.uuid4()}"
    await _pay(client, buyer, first["id"], "succeed", key)
    response = await _pay(client, buyer, second["id"], "succeed", key)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_key_reused"


async def test_same_key_from_another_user_is_independent(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer = await _paid_setup(session)
    other = await make_user(session)
    await session.commit()
    a = await _reserve(client, buyer, event, tt, qty=1)
    b = await _reserve(client, other, event, tt, qty=1)
    assert (await _pay(client, buyer, a["id"], "succeed", "shared-key-123")).status_code == 201
    assert (await _pay(client, other, b["id"], "succeed", "shared-key-123")).status_code == 201


async def test_failed_payment_no_tickets_and_releases(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, buyer = await _paid_setup(session, quantity_total=2)
    order = await _reserve(client, buyer, event, tt)

    response = await _pay(client, buyer, order["id"], "fail", f"fail-{uuid.uuid4()}")
    body = response.json()
    assert body["payment"]["status"] == "failed"
    assert "DEMO" in body["payment"]["failure_reason"]
    assert body["order"]["status"] == "failed"
    assert body["order"]["tickets"] == []
    assert await session.scalar(select(func.count()).select_from(Ticket)) == 0
    await session.refresh(tt)
    assert (tt.quantity_sold, tt.quantity_reserved) == (0, 0)

    assert [m.template for m in mail] == ["payment_failed"]
    assert "No real money" in mail[0].text

    # A failed order can't be paid later with a new key.
    retry = await _pay(client, buyer, order["id"], "succeed", f"late-{uuid.uuid4()}")
    assert retry.json()["error"]["code"] == "order_not_payable"


async def test_abandon_releases(client: httpx.AsyncClient, session: AsyncSession) -> None:
    event, tt, buyer = await _paid_setup(session, quantity_total=2)
    order = await _reserve(client, buyer, event, tt)
    response = await client.post(f"{ORDERS}/{order['id']}/abandon", headers=bearer(buyer))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    await session.refresh(tt)
    assert tt.quantity_reserved == 0
    again = await client.post(f"{ORDERS}/{order['id']}/abandon", headers=bearer(buyer))
    assert again.status_code == 409


async def test_expired_order_cannot_be_paid(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer = await _paid_setup(session)
    order = await _reserve(client, buyer, event, tt)
    row = await session.get_one(Order, order["id"])
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    response = await _pay(client, buyer, order["id"], "succeed", f"late-{uuid.uuid4()}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "order_expired"
    await session.refresh(row)
    assert row.status is OrderStatus.EXPIRED
    assert await session.scalar(select(func.count()).select_from(Payment)) == 0


async def test_paying_twice_with_new_keys_is_rejected(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer = await _paid_setup(session)
    order = await _reserve(client, buyer, event, tt)
    await _pay(client, buyer, order["id"], "succeed", f"one-{uuid.uuid4()}")
    second = await _pay(client, buyer, order["id"], "succeed", f"two-{uuid.uuid4()}")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "order_already_paid"
    assert await session.scalar(select(func.count()).select_from(Payment)) == 1


async def test_payment_needs_key_and_own_order(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer = await _paid_setup(session)
    stranger = await make_user(session)
    await session.commit()
    order = await _reserve(client, buyer, event, tt)
    no_key = await client.post(
        f"{ORDERS}/{order['id']}/payments", headers=bearer(buyer), json={"outcome": "succeed"}
    )
    assert no_key.status_code == 422
    theirs = await _pay(client, stranger, order["id"], "succeed", f"steal-{uuid.uuid4()}")
    assert theirs.status_code == 404


async def test_paid_checkout_blocked_until_activation(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    free = await make_ticket_type(session, event, price_kzt=0)
    paid = await make_ticket_type(session, event, price_kzt=5000)
    buyer = await make_user(session)
    await session.commit()

    def body(tt: TicketType) -> dict[str, object]:
        return {"event_id": str(event.id), "items": [{"ticket_type_id": str(tt.id), "quantity": 1}]}

    blocked = await client.post(ORDERS, headers=bearer(buyer), json=body(paid))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "paid_sales_not_active"
    # Free registration never needs activation (SRS 3.1).
    assert (await client.post(ORDERS, headers=bearer(buyer), json=body(free))).status_code == 201

    activation = await enable_paid_sales(session, event)
    await session.commit()
    assert (await client.post(ORDERS, headers=bearer(buyer), json=body(paid))).status_code == 201

    # A Platform Admin suspension closes paid checkout again (SRS 4.5).
    activation.status = ActivationStatus.SUSPENDED
    await session.commit()
    suspended = await client.post(ORDERS, headers=bearer(buyer), json=body(paid))
    assert suspended.json()["error"]["code"] == "paid_sales_not_active"


async def test_suspension_after_reserving_blocks_payment(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer = await _paid_setup(session)
    order = await _reserve(client, buyer, event, tt)
    activation = await session.scalar(
        select(PaidSalesActivation).where(PaidSalesActivation.event_id == event.id)
    )
    assert activation is not None
    activation.status = ActivationStatus.SUSPENDED
    await session.commit()
    response = await _pay(client, buyer, order["id"], "succeed", f"susp-{uuid.uuid4()}")
    assert response.json()["error"]["code"] == "paid_sales_not_active"


async def test_free_registration_emails_qr_ticket(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event = await make_published_event(session)
    free = await make_ticket_type(session, event, price_kzt=0)
    buyer = await make_user(session, locale="kk")
    await session.commit()
    response = await client.post(
        ORDERS,
        headers=bearer(buyer),
        json={
            "event_id": str(event.id),
            "items": [{"ticket_type_id": str(free.id), "quantity": 1}],
        },
    )
    assert response.json()["status"] == "confirmed"
    assert len(mail) == 1
    assert mail[0].subject.startswith("Билеттеріңіз")
    assert "Тегін тіркелу" in mail[0].text
    assert sum(a.mime_type == "image/png" for a in mail[0].attachments) == 1


async def test_processing_fee_recorded_for_organizer_not_charged_to_attendee(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer = await _paid_setup(session, price=10000)
    order = await _reserve(client, buyer, event, tt, qty=1)
    assert order["total_kzt"] == 10000
    paid = await _pay(client, buyer, order["id"], "succeed", f"fee-{uuid.uuid4()}")
    assert paid.json()["payment"]["amount_kzt"] == 10000
    row = await session.get_one(Order, order["id"])
    assert row.processing_fee_kzt == 300  # 3% (PROCESSING_FEE_BPS=300)
    assert (
        await session.get_one(Payment, paid.json()["payment"]["id"])
    ).status is PaymentStatus.SUCCEEDED
