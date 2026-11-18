"""Checkout: reserve inventory, confirm, issue tickets, and release what never confirms.

The inventory rules (SRS 4.3, 4.6) and how they hold under concurrency:

1. `create_order` locks the event row (`SELECT ... FOR UPDATE`) first. Checkouts for one
   event run one at a time from there, which is what makes the event-wide capacity check
   correct. Checkouts for different events don't wait on each other.
2. Each line then runs a conditional increment::

       UPDATE ticket_types SET quantity_reserved = quantity_reserved + :n
        WHERE id = :id AND quantity_sold + quantity_reserved + :n <= quantity_total

   No row updated means sold out. `ck_ticket_types_inventory_within_total` is the backstop
   if anything ever bypasses this path.
3. Free orders confirm in the same transaction. Paid orders hold the reservation until
   `expires_at`. Expired orders are released lazily (before every reservation for that event)
   and by a background sweep (`sweep_expired`), using `SKIP LOCKED` so the two never block.
"""

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal
from app.enums import EventStatus, EventVisibility, OrderStatus, TicketStatus
from app.errors import AppError
from app.models import (
    Attendee,
    Event,
    Order,
    OrderItem,
    OrganizerProfile,
    StaffAssignment,
    Ticket,
    TicketType,
    User,
)
from app.schemas.order import (
    AttendeeInput,
    EventSummary,
    MyTicketRead,
    OrderCreate,
    OrderItemRead,
    OrderRead,
    TicketRead,
)
from app.services import order_emails
from app.services.mail import Outbound
from app.tickets.numbers import order_reference, ticket_number
from app.tickets.tokens import sign_admission_token

logger = logging.getLogger(__name__)

OPEN_STATUSES = (OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT)


# --- visibility and sale checks ---------------------------------------------------------


async def is_owner_or_staff(session: AsyncSession, event: Event, user: User | None) -> bool:
    if user is None:
        return False
    owner = await session.scalar(
        select(OrganizerProfile.user_id).where(OrganizerProfile.id == event.organizer_profile_id)
    )
    if owner == user.id:
        return True
    return bool(
        await session.scalar(
            select(
                exists().where(
                    StaffAssignment.event_id == event.id,
                    StaffAssignment.user_id == user.id,
                    StaffAssignment.revoked_at.is_(None),
                )
            )
        )
    )


async def ensure_on_sale(session: AsyncSession, event: Event, user: User, now: datetime) -> None:
    """SRS 4.2: drafts and private events don't exist for outsiders (404); other reasons
    a published event can't sell are a 409 with a specific code."""
    hidden = event.status is EventStatus.DRAFT or (
        event.visibility is EventVisibility.PRIVATE
        and not await is_owner_or_staff(session, event, user)
    )
    if hidden:
        raise AppError(404, "event_not_found", "Event not found.")
    if event.status is not EventStatus.PUBLISHED:
        raise AppError(409, "event_not_on_sale", "This event isn't open for registration.")
    if event.is_suspended:
        raise AppError(409, "sales_suspended", "Sales for this event are suspended.")
    if event.registration_opens_at and now < event.registration_opens_at:
        raise AppError(409, "registration_not_open", "Registration hasn't opened yet.")
    if (event.registration_closes_at and now >= event.registration_closes_at) or (
        now >= event.ends_at
    ):
        raise AppError(409, "registration_closed", "Registration has closed.")


# --- creating orders ----------------------------------------------------------------------


async def create_order(
    session: AsyncSession, user: User, data: OrderCreate
) -> tuple[Order, Outbound]:
    now = datetime.now(UTC)
    event = await session.scalar(
        select(Event).where(Event.id == data.event_id).with_for_update(of=Event)
    )
    if event is None:
        raise AppError(404, "event_not_found", "Event not found.")
    await ensure_on_sale(session, event, user, now)
    await sweep_expired(session, event_id=event.id, now=now)

    requested = {item.ticket_type_id: item.quantity for item in data.items}
    if len(requested) != len(data.items):
        raise AppError(422, "duplicate_ticket_type", "List each ticket type once.")
    types = {
        t.id: t
        for t in await session.scalars(
            select(TicketType).where(TicketType.event_id == event.id, TicketType.id.in_(requested))
        )
    }
    for tt_id, qty in requested.items():
        tt = types.get(tt_id)
        if tt is None or tt.is_hidden:
            raise AppError(404, "ticket_type_not_found", "Ticket type not found.")
        if tt.sales_start_at and now < tt.sales_start_at:
            raise AppError(409, "sales_not_started", "Sales for this ticket haven't started.")
        if tt.sales_end_at and now >= tt.sales_end_at:
            raise AppError(409, "sales_ended", "Sales for this ticket have ended.")
        if qty > tt.max_per_order:
            raise AppError(422, "max_per_order_exceeded", f"At most {tt.max_per_order} per order.")

    if any(types[tt_id].price_kzt > 0 for tt_id in requested):
        from app.services.activation import ensure_paid_sales_enabled

        await ensure_paid_sales_enabled(session, event.id)

    total_quantity = sum(requested.values())
    attendees = _attendees_for(user, data.attendees, total_quantity)

    if event.capacity is not None:
        taken = await session.scalar(
            select(
                func.coalesce(func.sum(TicketType.quantity_sold + TicketType.quantity_reserved), 0)
            ).where(TicketType.event_id == event.id)
        )
        if (taken or 0) + total_quantity > event.capacity:
            raise AppError(409, "sold_out", "There aren't enough tickets left.")

    for tt_id, qty in requested.items():
        reserved = await session.scalar(
            update(TicketType)
            .where(
                TicketType.id == tt_id,
                TicketType.quantity_sold + TicketType.quantity_reserved + qty
                <= TicketType.quantity_total,
            )
            .values(quantity_reserved=TicketType.quantity_reserved + qty)
            .returning(TicketType.id)
        )
        if reserved is None:
            raise AppError(409, "sold_out", "There aren't enough tickets left.")

    order = Order(
        id=uuid.uuid4(),
        reference=await _unique_reference(session),
        user_id=user.id,
        event_id=event.id,
        status=OrderStatus.PENDING,
        currency=get_settings().currency,
    )
    session.add(order)
    # Attendee and OrderItem have no ORM relationship to Order, so the unit of work wouldn't
    # know to insert the order first. Flush it explicitly.
    await session.flush()
    # Ids are handed out in ascending order, so sorting items and attendees by id later
    # (when tickets are issued) reproduces the order they were listed in.
    item_ids = _ascending_ids(len(requested))
    attendee_ids = _ascending_ids(len(attendees))
    subtotal = 0
    for item_id, (tt_id, qty) in zip(item_ids, requested.items(), strict=True):
        tt = types[tt_id]
        line = tt.price_kzt * qty
        subtotal += line
        session.add(
            OrderItem(
                id=item_id,
                order_id=order.id,
                ticket_type_id=tt.id,
                quantity=qty,
                unit_price_kzt=tt.price_kzt,
                discount_kzt=0,
                line_total_kzt=line,
            )
        )
    for attendee_id, a in zip(attendee_ids, attendees, strict=True):
        session.add(
            Attendee(
                id=attendee_id,
                order_id=order.id,
                user_id=user.id if a.email and a.email.lower() == user.email.lower() else None,
                full_name=a.full_name,
                email=a.email,
                phone=a.phone,
            )
        )
    order.subtotal_kzt = subtotal
    order.discount_kzt = 0
    order.total_kzt = subtotal - order.discount_kzt
    await session.flush()

    # SRS 3.3: processing charges come out of the organizer's payout, never the attendee's
    # total. Recorded for the organizer's estimated-payout figures.
    order.processing_fee_kzt = order.total_kzt * get_settings().processing_fee_bps // 10_000

    outbound: Outbound = []
    if order.total_kzt == 0:
        # SRS 4.4: a free registration is a zero-total order, confirmed at once, with a
        # confirmation email carrying the QR tickets.
        await confirm_order(session, order, now)
        outbound = await order_emails.confirmation(session, order)
    else:
        order.status = OrderStatus.AWAITING_PAYMENT
        order.expires_at = now + timedelta(seconds=get_settings().order_reservation_ttl_seconds)
    await session.commit()
    return order, outbound


def _attendees_for(user: User, given: list[AttendeeInput], quantity: int) -> list[AttendeeInput]:
    if not given:
        return [
            AttendeeInput(full_name=user.full_name, email=user.email, phone=user.phone)
        ] * quantity
    if len(given) != quantity:
        raise AppError(
            422, "attendee_count_mismatch", "Enter one attendee for each ticket, or none."
        )
    return given


def _ascending_ids(n: int) -> list[uuid.UUID]:
    # Python compares UUIDs as 128-bit integers and Postgres compares them bytewise; both
    # give the same order.
    return sorted(uuid.uuid4() for _ in range(n))


async def _unique_reference(session: AsyncSession) -> str:
    # 31^6 references; a clash is rare, and uq_orders_reference backs this check.
    for _ in range(10):
        ref = order_reference()
        if not await session.scalar(select(exists().where(Order.reference == ref))):
            return ref
    raise AppError(500, "internal_error", "Could not allocate an order reference.")


# --- confirming and releasing ---------------------------------------------------------------


async def confirm_order(session: AsyncSession, order: Order, now: datetime | None = None) -> None:
    """Move the reservation to sold and issue one ticket per seat, each with its own signed
    admission token. Call inside the transaction that confirms payment (or creates a free
    order); never for an order that isn't open."""
    now = now or datetime.now(UTC)
    if order.status not in OPEN_STATUSES:
        raise AppError(409, "order_not_open", "This order can't be confirmed.")
    items = list(
        await session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
        )
    )
    attendees = list(
        await session.scalars(
            select(Attendee).where(Attendee.order_id == order.id).order_by(Attendee.id)
        )
    )
    # Ascending ids again, so tickets list in the same order as their attendees.
    ticket_ids = iter(_ascending_ids(sum(i.quantity for i in items)))
    slot = 0
    for item in items:
        await session.execute(
            update(TicketType)
            .where(TicketType.id == item.ticket_type_id)
            .values(
                quantity_reserved=TicketType.quantity_reserved - item.quantity,
                quantity_sold=TicketType.quantity_sold + item.quantity,
            )
        )
        per_ticket_price = item.line_total_kzt // item.quantity
        for _ in range(item.quantity):
            ticket_id = next(ticket_ids)
            session.add(
                Ticket(
                    id=ticket_id,
                    ticket_number=ticket_number(),
                    order_id=order.id,
                    order_item_id=item.id,
                    event_id=order.event_id,
                    ticket_type_id=item.ticket_type_id,
                    attendee_id=attendees[slot].id,
                    status=TicketStatus.VALID,
                    admission_token=sign_admission_token(ticket_id),
                    price_kzt=per_ticket_price,
                    issued_at=now,
                )
            )
            slot += 1
    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = now
    order.expires_at = None
    await session.flush()


async def release_order(session: AsyncSession, order: Order, status: OrderStatus) -> None:
    """Return an open order's reservation to stock and close it as failed, cancelled or
    expired. Failed or abandoned checkouts never yield tickets (SRS 4.6)."""
    if order.status not in OPEN_STATUSES:
        return
    items = await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
    for item in items:
        await session.execute(
            update(TicketType)
            .where(TicketType.id == item.ticket_type_id)
            .values(quantity_reserved=TicketType.quantity_reserved - item.quantity)
        )
    order.status = status
    if status is OrderStatus.CANCELLED:
        order.cancelled_at = datetime.now(UTC)
    await session.flush()


async def sweep_expired(
    session: AsyncSession,
    *,
    event_id: uuid.UUID | None = None,
    now: datetime | None = None,
    limit: int = 200,
) -> int:
    """Expire open orders past `expires_at`. Skips rows another transaction holds (that one
    is paying or releasing it). Does not commit."""
    now = now or datetime.now(UTC)
    query = (
        select(Order)
        .where(
            Order.status.in_(OPEN_STATUSES), Order.expires_at.is_not(None), Order.expires_at <= now
        )
        .order_by(Order.expires_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    if event_id is not None:
        query = query.where(Order.event_id == event_id)
    expired = list(await session.scalars(query))
    for order in expired:
        await release_order(session, order, OrderStatus.EXPIRED)
    return len(expired)


async def run_expiry_sweeper(interval_seconds: float) -> None:
    """Background task started by the app lifespan. Cleanup only: correctness never depends
    on it, because every reservation sweeps its own event first."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with SessionLocal() as session:
                released = await sweep_expired(session)
                await session.commit()
            if released:
                logger.info("Released %d expired order(s)", released)
        except Exception:
            logger.exception("Order expiry sweep failed")


@contextlib.asynccontextmanager
async def expiry_sweeper(interval_seconds: float) -> AsyncIterator[None]:
    task = (
        asyncio.create_task(run_expiry_sweeper(interval_seconds)) if interval_seconds > 0 else None
    )
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


# --- reading --------------------------------------------------------------------------------


def _event_summary(event: Event) -> EventSummary:
    venue = event.venue
    return EventSummary(
        id=event.id,
        title=event.title,
        slug=event.slug,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        timezone=event.timezone,
        venue_name=venue.name if venue else None,
        venue_address=", ".join(p for p in (venue.address_line1, venue.city) if p)
        if venue
        else None,
    )


async def tickets_read(session: AsyncSession, tickets: Sequence[Ticket]) -> list[TicketRead]:
    if not tickets:
        return []
    names = dict(
        (
            await session.execute(
                select(TicketType.id, TicketType.name).where(
                    TicketType.id.in_({t.ticket_type_id for t in tickets})
                )
            )
        )
        .tuples()
        .all()
    )
    people = {
        a.id: a
        for a in await session.scalars(
            select(Attendee).where(Attendee.id.in_({t.attendee_id for t in tickets}))
        )
    }
    return [
        TicketRead(
            id=t.id,
            ticket_number=t.ticket_number,
            status=t.status,
            ticket_type_id=t.ticket_type_id,
            ticket_type_name=names[t.ticket_type_id],
            attendee_name=people[t.attendee_id].full_name,
            attendee_email=people[t.attendee_id].email,
            seat_section=t.seat_section,
            seat_row=t.seat_row,
            seat_number=t.seat_number,
            qr_payload=t.admission_token,
            issued_at=t.issued_at,
            checked_in_at=t.checked_in_at,
        )
        for t in tickets
    ]


async def order_read(session: AsyncSession, order: Order) -> OrderRead:
    event = await session.get_one(Event, order.event_id)
    items = list(
        await session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
        )
    )
    names = dict(
        (
            await session.execute(
                select(TicketType.id, TicketType.name).where(
                    TicketType.id.in_({i.ticket_type_id for i in items})
                )
            )
        )
        .tuples()
        .all()
    )
    tickets = list(
        await session.scalars(select(Ticket).where(Ticket.order_id == order.id).order_by(Ticket.id))
    )
    return OrderRead(
        id=order.id,
        reference=order.reference,
        status=order.status,
        event=_event_summary(event),
        subtotal_kzt=order.subtotal_kzt,
        discount_kzt=order.discount_kzt,
        total_kzt=order.total_kzt,
        currency=order.currency,
        payment_required=order.status is OrderStatus.AWAITING_PAYMENT,
        expires_at=order.expires_at,
        confirmed_at=order.confirmed_at,
        created_at=order.created_at,
        items=[
            OrderItemRead(
                id=i.id,
                ticket_type_id=i.ticket_type_id,
                ticket_type_name=names[i.ticket_type_id],
                quantity=i.quantity,
                unit_price_kzt=i.unit_price_kzt,
                discount_kzt=i.discount_kzt,
                line_total_kzt=i.line_total_kzt,
            )
            for i in items
        ],
        tickets=await tickets_read(session, tickets),
    )


async def get_own_order(session: AsyncSession, user: User, order_id: uuid.UUID) -> Order:
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user.id)
    )
    if order is None:
        raise AppError(404, "order_not_found", "Order not found.")
    return order


async def list_own_orders(session: AsyncSession, user: User) -> list[Order]:
    return list(
        await session.scalars(
            select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
        )
    )


async def list_own_tickets(session: AsyncSession, user: User) -> list[MyTicketRead]:
    rows = (
        (
            await session.execute(
                select(Ticket, Order.reference)
                .join(Order, Order.id == Ticket.order_id)
                .join(Event, Event.id == Ticket.event_id)
                .where(Order.user_id == user.id)
                .order_by(Event.starts_at, Ticket.order_id, Ticket.id)
            )
        )
        .tuples()
        .all()
    )
    tickets = [t for t, _ in rows]
    reads = await tickets_read(session, tickets)
    events = (
        {
            e.id: e
            for e in await session.scalars(
                select(Event).where(Event.id.in_({t.event_id for t in tickets}))
            )
        }
        if tickets
        else {}
    )
    return [
        MyTicketRead(
            **read.model_dump(),
            order_id=ticket.order_id,
            order_reference=ref,
            event=_event_summary(events[ticket.event_id]),
        )
        for read, (ticket, ref) in zip(reads, rows, strict=True)
    ]


async def get_own_ticket(session: AsyncSession, user: User, ticket_id: uuid.UUID) -> Ticket:
    ticket = await session.scalar(
        select(Ticket)
        .join(Order, Order.id == Ticket.order_id)
        .where(Ticket.id == ticket_id, Order.user_id == user.id)
    )
    if ticket is None:
        raise AppError(404, "ticket_not_found", "Ticket not found.")
    return ticket
