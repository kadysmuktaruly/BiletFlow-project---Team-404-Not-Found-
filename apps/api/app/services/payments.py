"""The DEMO payment provider (SRS 3.2, 4.6). No real money moves, ever.

Idempotency: the client sends an `Idempotency-Key` header with each attempt. It is stored,
scoped to the user, in `payments.idempotency_key` (unique). A retry with the same key finds
that row and gets the original outcome back, so a dropped connection or a double click can
never charge twice or issue a second set of tickets. Two requests racing with the same key
both try to insert; the unique constraint lets one win and the other replays its result.
"""

import secrets
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import OrderStatus, PaymentPurpose, PaymentStatus
from app.errors import AppError
from app.models import Order, Payment, User
from app.schemas.payment import PaymentRead
from app.services import audit, order_emails
from app.services.mail import Outbound
from app.services.orders import confirm_order, release_order

Outcome = Literal["succeed", "fail"]
SIMULATED_DECLINE = "Simulated decline (DEMO): no real card was charged."


def scoped_key(user: User, key: str) -> str:
    return f"{user.id}:{key}"


def payment_read(payment: Payment) -> PaymentRead:
    return PaymentRead.model_validate(payment, from_attributes=True)


async def find_by_key(session: AsyncSession, user: User, key: str) -> Payment | None:
    result = await session.scalars(
        select(Payment).where(Payment.idempotency_key == scoped_key(user, key))
    )
    return result.first()


def replay_or_conflict(
    payment: Payment,
    purpose: PaymentPurpose,
    *,
    order_id: uuid.UUID | None,
    event_id: uuid.UUID | None,
) -> Payment:
    if (
        payment.purpose is not purpose
        or (order_id is not None and payment.order_id != order_id)
        or (event_id is not None and payment.event_id != event_id)
    ):
        raise AppError(
            409,
            "idempotency_key_reused",
            "This Idempotency-Key was already used for a different payment.",
        )
    return payment


def new_payment(
    user: User,
    key: str,
    purpose: PaymentPurpose,
    amount: int,
    outcome: Outcome,
    *,
    order_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> Payment:
    now = datetime.now(UTC)
    ok = outcome == "succeed"
    return Payment(
        id=uuid.uuid4(),
        purpose=purpose,
        status=PaymentStatus.SUCCEEDED if ok else PaymentStatus.FAILED,
        order_id=order_id,
        event_id=event_id,
        user_id=user.id,
        amount_kzt=amount,
        currency=get_settings().currency,
        provider="simulated",
        provider_reference=f"SIM-{secrets.token_hex(6).upper()}",
        card_brand="DEMO",
        card_last4="4242",
        is_simulated=True,
        idempotency_key=scoped_key(user, key),
        failure_reason=None if ok else SIMULATED_DECLINE,
        succeeded_at=now if ok else None,
    )


async def insert_payment(session: AsyncSession, payment: Payment) -> bool:
    """Insert inside a savepoint. False if another request already used this key."""
    try:
        async with session.begin_nested():
            session.add(payment)
            await session.flush()
    except IntegrityError:
        return False
    return True


# --- ticket orders ----------------------------------------------------------------------------


async def pay_order(
    session: AsyncSession, user: User, order_id: uuid.UUID, key: str, outcome: Outcome
) -> tuple[Order, Payment, bool, Outbound]:
    """Returns (order, payment, replayed, emails to send after commit)."""
    from app.services.activation import ensure_paid_sales_enabled

    existing = await find_by_key(session, user, key)
    if existing is not None:
        payment = replay_or_conflict(
            existing, PaymentPurpose.TICKET_ORDER, order_id=order_id, event_id=None
        )
        order = await session.get_one(Order, order_id)
        return order, payment, True, []

    # One payment attempt per order at a time.
    locked = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user.id).with_for_update()
    )
    if locked is None:
        raise AppError(404, "order_not_found", "Order not found.")
    order = locked
    # A concurrent retry with this key may have finished while we waited for the lock.
    winner = await find_by_key(session, user, key)
    if winner is not None:
        replay_or_conflict(winner, PaymentPurpose.TICKET_ORDER, order_id=order_id, event_id=None)
        return order, winner, True, []
    if order.status is OrderStatus.CONFIRMED:
        raise AppError(409, "order_already_paid", "This order has already been paid.")
    if order.status is not OrderStatus.AWAITING_PAYMENT:
        raise AppError(409, "order_not_payable", "This order can no longer be paid.")
    now = datetime.now(UTC)
    if order.expires_at is not None and order.expires_at <= now:
        await release_order(session, order, OrderStatus.EXPIRED)
        await session.commit()
        raise AppError(409, "order_expired", "The reservation expired. Please start again.")
    await ensure_paid_sales_enabled(session, order.event_id)

    payment = new_payment(
        user,
        key,
        PaymentPurpose.TICKET_ORDER,
        order.total_kzt,
        outcome,
        order_id=order.id,
        event_id=order.event_id,
    )
    if not await insert_payment(session, payment):
        await session.rollback()
        raced = await find_by_key(session, user, key)
        assert raced is not None
        replay_or_conflict(raced, PaymentPurpose.TICKET_ORDER, order_id=order_id, event_id=None)
        return await session.get_one(Order, order_id), raced, True, []

    if outcome == "succeed":
        await confirm_order(session, order, now)
        outbound = await order_emails.confirmation(session, order)
        action, description = "payment.succeeded", f"DEMO payment for order {order.reference}"
    else:
        # SRS 4.6: a failed transaction never yields a valid ticket; the stock goes back.
        await release_order(session, order, OrderStatus.FAILED)
        outbound = await order_emails.payment_failed(session, order)
        action, description = "payment.failed", f"DEMO payment failed for order {order.reference}"
    audit.record(
        session,
        actor_id=user.id,
        action=action,
        entity_type="payment",
        entity_id=payment.id,
        description=f"{description}: {order.total_kzt} KZT",
        event_id=order.event_id,
    )
    await session.commit()
    return order, payment, False, outbound


async def abandon_order(session: AsyncSession, user: User, order_id: uuid.UUID) -> Order:
    """The attendee leaves the DEMO payment screen: release the tickets now rather than at
    expiry (SRS 4.6: abandoned transactions don't create tickets)."""
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user.id).with_for_update()
    )
    if order is None:
        raise AppError(404, "order_not_found", "Order not found.")
    if order.status is not OrderStatus.AWAITING_PAYMENT:
        raise AppError(409, "order_not_payable", "This order is no longer open.")
    await release_order(session, order, OrderStatus.CANCELLED)
    await session.commit()
    return order
