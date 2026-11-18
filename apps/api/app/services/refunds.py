"""Orders, refunds and cancellations from the organizer's side (SRS 4.9). DEMO only.

* **Full refunds of paid orders**, through the same simulated provider as payments. The
  `Idempotency-Key` is stored per user in `refunds.idempotency_key` (unique), so a retry or a
  double click returns the first result instead of refunding twice; two requests racing with
  one key both try to insert and the loser replays the winner.
* **Cancelling free registrations.** A free order has nothing to refund; it is cancelled.
* Either way the order's tickets become invalid at once (check-in reads live status), go
  back on sale unless the event is cancelled, the action is audited (SRS 4.9 "All payment and
  refund actions shall be recorded in an audit log") and the buyer is notified (SRS 4.10).
* **Cancelling an event** refunds every paid order automatically (`refund_for_event_cancel`).
"""

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import (
    EventStatus,
    NotificationType,
    OrderStatus,
    PaymentPurpose,
    PaymentStatus,
    RefundStatus,
    TicketStatus,
)
from app.errors import AppError
from app.models import Event, Order, Payment, PromoCode, Refund, Ticket, TicketType, User
from app.schemas.refund import OrganizerOrderList, OrganizerOrderRead, RefundRead
from app.services import audit
from app.services.mail import Outbound
from app.services.notifications import Message, notify
from app.services.order_emails import format_kzt

# Tickets an order still "holds": everything except those already refunded or cancelled.
_LIVE = (TicketStatus.VALID, TicketStatus.CHECKED_IN)
LIST_LIMIT = 200


def _scoped(user: User, key: str) -> str:
    return f"{user.id}:{key}"


def refund_read(refund: Refund) -> RefundRead:
    return RefundRead.model_validate(refund, from_attributes=True)


# --- the organizer's order list -----------------------------------------------------------


def _can_refund(order: Order, event: Event) -> bool:
    return order.status is OrderStatus.CONFIRMED and order.total_kzt > 0


def _can_cancel(order: Order) -> bool:
    return order.status is OrderStatus.CONFIRMED and order.total_kzt == 0


async def order_reads(
    session: AsyncSession, event: Event, orders: list[Order]
) -> list[OrganizerOrderRead]:
    if not orders:
        return []
    ids = [o.id for o in orders]
    buyers = {
        u.id: u
        for u in await session.scalars(select(User).where(User.id.in_({o.user_id for o in orders})))
    }
    counts = dict(
        (
            await session.execute(
                select(Ticket.order_id, func.count(Ticket.id))
                .where(Ticket.order_id.in_(ids))
                .group_by(Ticket.order_id)
            )
        )
        .tuples()
        .all()
    )
    codes = dict(
        (
            await session.execute(
                select(PromoCode.id, PromoCode.code).where(
                    PromoCode.id.in_({o.promo_code_id for o in orders if o.promo_code_id})
                )
            )
        )
        .tuples()
        .all()
    )
    return [
        OrganizerOrderRead(
            id=o.id,
            reference=o.reference,
            status=o.status,
            buyer_name=buyers[o.user_id].full_name,
            buyer_email=buyers[o.user_id].email,
            # Paid orders that never completed have no tickets; show what they asked for.
            tickets=counts.get(o.id, 0),
            subtotal_kzt=o.subtotal_kzt,
            discount_kzt=o.discount_kzt,
            total_kzt=o.total_kzt,
            refunded_kzt=o.refunded_kzt,
            processing_fee_kzt=o.processing_fee_kzt,
            promo_code=codes.get(o.promo_code_id) if o.promo_code_id else None,
            created_at=o.created_at,
            confirmed_at=o.confirmed_at,
            cancelled_at=o.cancelled_at,
            can_refund=_can_refund(o, event),
            can_cancel=_can_cancel(o),
        )
        for o in orders
    ]


async def list_orders(
    session: AsyncSession, event: Event, q: str | None, status: OrderStatus | None
) -> OrganizerOrderList:
    query = select(Order).join(User, User.id == Order.user_id).where(Order.event_id == event.id)
    term = (q or "").strip()
    if term:
        pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                Order.reference.ilike(pattern, escape="\\"),
                User.full_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
            )
        )
    if status is not None:
        query = query.where(Order.status == status)
    orders = list(
        await session.scalars(query.order_by(Order.created_at.desc()).limit(LIST_LIMIT + 1))
    )
    return OrganizerOrderList(
        orders=await order_reads(session, event, orders[:LIST_LIMIT]),
        truncated=len(orders) > LIST_LIMIT,
    )


async def _locked_order(session: AsyncSession, event: Event, order_id: uuid.UUID) -> Order:
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.event_id == event.id).with_for_update()
    )
    if order is None:
        raise AppError(404, "order_not_found", "Order not found.")
    return order


async def _invalidate_tickets(
    session: AsyncSession, event: Event, order: Order, status: TicketStatus, now: datetime
) -> int:
    """Mark the order's tickets refunded or cancelled. Unless the event itself is cancelled,
    return them to sale (SRS 4.3 counts: sold goes down, refunded goes up)."""
    stamp = {"refunded_at": now} if status is TicketStatus.REFUNDED else {"cancelled_at": now}
    tickets = list(
        await session.scalars(
            select(Ticket).where(Ticket.order_id == order.id, Ticket.status != status)
        )
    )
    per_type: dict[uuid.UUID, int] = {}
    for ticket in tickets:
        if ticket.status in _LIVE:
            per_type[ticket.ticket_type_id] = per_type.get(ticket.ticket_type_id, 0) + 1
    await session.execute(
        update(Ticket)
        .where(Ticket.order_id == order.id, Ticket.status != status)
        .values(status=status, **stamp)
    )
    if event.status is not EventStatus.CANCELLED:
        for tt_id, n in per_type.items():
            await session.execute(
                update(TicketType)
                .where(TicketType.id == tt_id)
                .values(quantity_sold=TicketType.quantity_sold - n)
            )
    return len(tickets)


# --- refunds --------------------------------------------------------------------------------


async def refund_order(
    session: AsyncSession,
    actor: User,
    event: Event,
    order_id: uuid.UUID,
    key: str,
    reason: str | None,
    *,
    commit: bool = True,
) -> tuple[Order, Refund, bool, Outbound]:
    """Refund a paid order in full. Returns (order, refund, replayed, emails to send)."""
    scoped = _scoped(actor, key)
    existing = await session.scalar(select(Refund).where(Refund.idempotency_key == scoped))
    if existing is not None:
        return await _replay(session, existing, order_id)

    order = await _locked_order(session, event, order_id)
    # A concurrent retry with this key may have finished while we waited for the lock.
    winner = await session.scalar(select(Refund).where(Refund.idempotency_key == scoped))
    if winner is not None:
        return await _replay(session, winner, order_id)
    if order.status is OrderStatus.REFUNDED:
        raise AppError(409, "order_already_refunded", "This order has already been refunded.")
    if order.status is not OrderStatus.CONFIRMED or order.total_kzt == 0:
        raise AppError(
            409,
            "order_not_refundable",
            "Only paid, confirmed orders can be refunded. Free registrations are cancelled.",
        )
    payment = await session.scalar(
        select(Payment)
        .where(
            Payment.order_id == order.id,
            Payment.purpose == PaymentPurpose.TICKET_ORDER,
            Payment.status == PaymentStatus.SUCCEEDED,
        )
        .order_by(Payment.created_at.desc())
    )
    if payment is None:
        raise AppError(409, "order_not_refundable", "This order has no completed payment.")

    now = datetime.now(UTC)
    amount = order.total_kzt - order.refunded_kzt
    refund = Refund(
        id=uuid.uuid4(),
        payment_id=payment.id,
        order_id=order.id,
        status=RefundStatus.SUCCEEDED,
        amount_kzt=amount,
        currency=get_settings().currency,
        reason=reason,
        initiated_by_user_id=actor.id,
        is_simulated=True,
        idempotency_key=scoped,
        provider_reference=f"SIM-R-{secrets.token_hex(6).upper()}",
        succeeded_at=now,
    )
    try:
        async with session.begin_nested():
            session.add(refund)
            await session.flush()
    except IntegrityError:
        # Lost a race on the same key: replay the winner.
        winner = await session.scalar(select(Refund).where(Refund.idempotency_key == scoped))
        assert winner is not None
        return await _replay(session, winner, order_id)

    payment.status = PaymentStatus.REFUNDED
    order.status = OrderStatus.REFUNDED
    order.refunded_kzt = order.total_kzt
    count = await _invalidate_tickets(session, event, order, TicketStatus.REFUNDED, now)
    audit.record(
        session,
        actor_id=actor.id,
        action="order.refunded",
        entity_type="order",
        entity_id=order.id,
        description=f"DEMO refund of {format_kzt(amount)} for order {order.reference} "
        f"({count} ticket(s) invalidated)" + (f". Reason: {reason}" if reason else ""),
        event_id=event.id,
    )
    buyer = await session.get_one(User, order.user_id)
    outbound = await notify(
        session,
        buyer,
        Message(
            type=NotificationType.REFUND_COMPLETED,
            template="refund_completed",
            params={
                "event": event.title,
                "reference": order.reference,
                "amount": format_kzt(amount),
            },
            action_path=f"/orders/{order.id}",
            event_id=event.id,
            order_id=order.id,
        ),
    )
    if commit:
        await session.commit()
    return order, refund, False, outbound


async def _replay(
    session: AsyncSession, refund: Refund, order_id: uuid.UUID
) -> tuple[Order, Refund, bool, Outbound]:
    if refund.order_id != order_id:
        raise AppError(
            409,
            "idempotency_key_reused",
            "This Idempotency-Key was already used for a different refund.",
        )
    order = await session.get_one(Order, order_id)
    return order, refund, True, []


async def refund_for_event_cancel(session: AsyncSession, actor: User, event: Event) -> Outbound:
    """SRS 4.9 (semester plan): cancelling an event refunds every paid order in full. Runs in
    the cancellation's transaction; the key is fixed per order, so it can never refund twice."""
    paid = list(
        await session.scalars(
            select(Order.id).where(
                Order.event_id == event.id,
                Order.status == OrderStatus.CONFIRMED,
                Order.total_kzt > 0,
            )
        )
    )
    outbound: Outbound = []
    for order_id in paid:
        _, _, _, emails = await refund_order(
            session,
            actor,
            event,
            order_id,
            f"event-cancel:{order_id}",
            "Event cancelled",
            commit=False,
        )
        outbound += emails
    return outbound


# --- free registrations ---------------------------------------------------------------------


async def cancel_registration(
    session: AsyncSession, actor: User, event: Event, order_id: uuid.UUID, reason: str | None
) -> tuple[Order, Outbound]:
    """SRS 4.9: "Organizers shall be able to cancel free registrations"."""
    order = await _locked_order(session, event, order_id)
    if order.status is not OrderStatus.CONFIRMED or order.total_kzt != 0:
        raise AppError(
            409,
            "order_not_cancellable",
            "Only confirmed free registrations can be cancelled. Paid orders are refunded.",
        )
    now = datetime.now(UTC)
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = now
    count = await _invalidate_tickets(session, event, order, TicketStatus.CANCELLED, now)
    audit.record(
        session,
        actor_id=actor.id,
        action="order.registration_cancelled",
        entity_type="order",
        entity_id=order.id,
        description=f"Cancelled free registration {order.reference} ({count} ticket(s))"
        + (f". Reason: {reason}" if reason else ""),
        event_id=event.id,
    )
    buyer = await session.get_one(User, order.user_id)
    outbound = await notify(
        session,
        buyer,
        Message(
            type=NotificationType.EVENT_UPDATE,
            template="registration_cancelled",
            params={"event": event.title, "reference": order.reference},
            action_path=f"/orders/{order.id}",
            event_id=event.id,
            order_id=order.id,
        ),
    )
    await session.commit()
    return order, outbound
