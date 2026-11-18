"""Organizer-side ticket type management (SRS 4.3)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TicketStatus
from app.errors import AppError
from app.models import Event, OrderItem, Ticket, TicketType, User
from app.schemas.event import localize
from app.schemas.ticket_type import (
    PublicTicketTypeRead,
    TicketTypeCreate,
    TicketTypeRead,
    TicketTypeUpdate,
)
from app.services import audit


def available(tt: TicketType) -> int:
    return max(tt.quantity_total - tt.quantity_sold - tt.quantity_reserved, 0)


def on_sale(tt: TicketType, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return (
        not tt.is_hidden
        and (tt.sales_start_at is None or tt.sales_start_at <= now)
        and (tt.sales_end_at is None or now < tt.sales_end_at)
    )


async def to_read(session: AsyncSession, types: list[TicketType]) -> list[TicketTypeRead]:
    """Attach refunded and checked-in counts, which come from the tickets themselves."""
    counts: dict[tuple[object, TicketStatus], int] = {}
    if types:
        rows = await session.execute(
            select(Ticket.ticket_type_id, Ticket.status, func.count())
            .where(Ticket.ticket_type_id.in_([t.id for t in types]))
            .where(Ticket.status.in_([TicketStatus.REFUNDED, TicketStatus.CHECKED_IN]))
            .group_by(Ticket.ticket_type_id, Ticket.status)
        )
        counts = {(tt_id, status): n for tt_id, status, n in rows.tuples().all()}
    return [
        TicketTypeRead.model_validate(
            {
                **{c: getattr(t, c) for c in TicketTypeRead.model_fields if hasattr(t, c)},
                "is_free": t.price_kzt == 0,
                "quantity_available": available(t),
                "quantity_refunded": counts.get((t.id, TicketStatus.REFUNDED), 0),
                "quantity_checked_in": counts.get((t.id, TicketStatus.CHECKED_IN), 0),
            }
        )
        for t in types
    ]


def to_public(t: TicketType) -> PublicTicketTypeRead:
    return PublicTicketTypeRead.model_validate(
        {
            **{c: getattr(t, c) for c in PublicTicketTypeRead.model_fields if hasattr(t, c)},
            "is_free": t.price_kzt == 0,
            "quantity_available": available(t),
            "on_sale": on_sale(t),
        }
    )


async def list_for_event(session: AsyncSession, event: Event) -> list[TicketType]:
    result = await session.scalars(
        select(TicketType).where(TicketType.event_id == event.id).order_by(TicketType.created_at)
    )
    return list(result)


async def get_for_event(session: AsyncSession, event: Event, ticket_type_id: object) -> TicketType:
    tt = await session.scalar(
        select(TicketType).where(TicketType.id == ticket_type_id, TicketType.event_id == event.id)
    )
    if tt is None:
        raise AppError(404, "ticket_type_not_found", "Ticket type not found.")
    return tt


def _check_window(tt: TicketType) -> None:
    if tt.sales_start_at and tt.sales_end_at and tt.sales_end_at <= tt.sales_start_at:
        raise AppError(422, "invalid_sales_window", "Sales must end after they start.")


def _ensure_editable(event: Event) -> None:
    from app.services.events import EDITABLE_STATUSES

    if event.status not in EDITABLE_STATUSES:
        raise AppError(409, "event_not_editable", "Cancelled or completed events can't be edited.")


async def create(
    session: AsyncSession, event: Event, user: User, data: TicketTypeCreate
) -> TicketType:
    _ensure_editable(event)
    tz = ZoneInfo(event.timezone)
    values = data.model_dump()
    for field in ("sales_start_at", "sales_end_at"):
        if values[field] is not None:
            values[field] = localize(values[field], tz)
    tt = TicketType(event_id=event.id, quantity_sold=0, quantity_reserved=0, **values)
    _check_window(tt)
    session.add(tt)
    await session.flush()
    audit.record(
        session,
        actor_id=user.id,
        action="ticket_type.created",
        entity_type="ticket_type",
        entity_id=tt.id,
        description=f"Created ticket type “{tt.name}” at {tt.price_kzt} KZT × {tt.quantity_total}",
        event_id=event.id,
    )
    await session.commit()
    return tt


async def update(
    session: AsyncSession, event: Event, tt: TicketType, user: User, data: TicketTypeUpdate
) -> TicketType:
    _ensure_editable(event)
    # Lock the row so a concurrent checkout can't reserve against a quantity we're shrinking.
    await session.refresh(tt, with_for_update=True)
    changes = data.model_dump(exclude_unset=True)
    tz = ZoneInfo(event.timezone)
    old_price, old_quantity = tt.price_kzt, tt.quantity_total

    for field, value in changes.items():
        if value is None and field in (
            "name",
            "price_kzt",
            "quantity_total",
            "max_per_order",
            "is_hidden",
        ):
            continue  # required columns can't be cleared
        if field in ("sales_start_at", "sales_end_at") and value is not None:
            value = localize(value, tz)
        setattr(tt, field, value)
    _check_window(tt)
    if tt.quantity_total < tt.quantity_sold + tt.quantity_reserved:
        raise AppError(
            409,
            "quantity_below_sold",
            "The quantity can't be lower than the tickets already sold or reserved.",
        )

    # SRS 4.16: price and capacity changes belong on the event timeline.
    if tt.price_kzt != old_price:
        audit.record(
            session,
            actor_id=user.id,
            action="ticket_type.price_changed",
            entity_type="ticket_type",
            entity_id=tt.id,
            description=f"“{tt.name}” price changed from {old_price} to {tt.price_kzt} KZT",
            event_id=event.id,
        )
    if tt.quantity_total != old_quantity:
        audit.record(
            session,
            actor_id=user.id,
            action="ticket_type.quantity_changed",
            entity_type="ticket_type",
            entity_id=tt.id,
            description=f"“{tt.name}” quantity changed from {old_quantity} to {tt.quantity_total}",
            event_id=event.id,
        )
    await session.commit()
    return tt


async def delete(session: AsyncSession, event: Event, tt: TicketType, user: User) -> None:
    _ensure_editable(event)
    has_orders = await session.scalar(
        select(func.count()).select_from(OrderItem).where(OrderItem.ticket_type_id == tt.id)
    )
    if has_orders:
        raise AppError(
            409,
            "ticket_type_has_orders",
            "This ticket type has orders. Hide it instead of deleting it.",
        )
    audit.record(
        session,
        actor_id=user.id,
        action="ticket_type.deleted",
        entity_type="ticket_type",
        entity_id=tt.id,
        description=f"Deleted ticket type “{tt.name}”",
        event_id=event.id,
    )
    await session.delete(tt)
    await session.commit()
