"""Basic organizer analytics (SRS 4.15), computed from authoritative BiletFlow records.

* **Scoped to the organizer's own events** (the router passes only their events).
* **Never slows checkout** (SRS 7): the queries run in a `READ ONLY` transaction with a
  statement timeout, take no row locks, and only read; checkout's `FOR UPDATE` locks and
  conditional updates never wait on them. `tests/test_analytics.py` checks that a checkout
  completes while an analytics transaction is open.
* Order-based figures (sales, revenue, campaigns, sales over time) use orders **confirmed**
  in the date range, counted per order line so the ticket-type filter applies exactly. A
  refunded order counts in gross and again under refunds; the chart and the per-type
  figures show only sales that stand. Capacity and attendance are the current state.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import OrderStatus, TicketStatus
from app.errors import AppError
from app.models import (
    Event,
    Order,
    OrderItem,
    OrganizerProfile,
    PromoCode,
    PromoRedemption,
    PromotionalCampaign,
    Ticket,
    TicketType,
)
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsRead,
    AttendanceFigures,
    CampaignFigures,
    CapacityFigures,
    DayPoint,
    RevenueFigures,
    TicketTypeFigures,
)

DEFAULT_DAYS = 30
MAX_DAYS = 366
DEFAULT_ZONE = "Asia/Almaty"
_SOLD = (OrderStatus.CONFIRMED, OrderStatus.REFUNDED)


def _percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


async def compute(
    session: AsyncSession,
    organizer: OrganizerProfile,
    *,
    event_id: uuid.UUID | None,
    ticket_type_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> AnalyticsRead:
    # Finish whatever the request did so far (e.g. a lazily created organizer profile), so
    # the analytics run in a fresh transaction that is read-only and time-boxed: it can
    # never hold a lock checkout waits on.
    await session.commit()
    await session.execute(text("SET TRANSACTION READ ONLY"))
    await session.execute(text("SET LOCAL statement_timeout = '5s'"))
    try:
        return await _compute(session, organizer, event_id, ticket_type_id, date_from, date_to)
    finally:
        await session.rollback()


async def _compute(
    session: AsyncSession,
    organizer: OrganizerProfile,
    event_id: uuid.UUID | None,
    ticket_type_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> AnalyticsRead:
    events = list(
        await session.scalars(
            select(Event)
            .where(Event.organizer_profile_id == organizer.id)
            .order_by(Event.starts_at)
        )
    )
    if event_id is not None:
        events = [e for e in events if e.id == event_id]
        if not events:
            raise AppError(404, "event_not_found", "Event not found.")
    event_ids = [e.id for e in events]
    types = (
        list(
            await session.scalars(
                select(TicketType)
                .where(TicketType.event_id.in_(event_ids))
                .order_by(TicketType.name)
            )
        )
        if event_ids
        else []
    )
    if ticket_type_id is not None:
        types = [t for t in types if t.id == ticket_type_id]
        if not types:
            raise AppError(404, "ticket_type_not_found", "Ticket type not found.")
    type_ids = [t.id for t in types]

    zone_name = events[0].timezone if len(events) == 1 else DEFAULT_ZONE
    zone = ZoneInfo(zone_name)
    today = datetime.now(zone).date()
    end = date_to or today
    start = date_from or end - timedelta(days=DEFAULT_DAYS - 1)
    if end < start:
        raise AppError(422, "invalid_date_range", "The end date must not be before the start.")
    if (end - start).days >= MAX_DAYS:
        raise AppError(422, "invalid_date_range", f"Pick at most {MAX_DAYS} days.")
    lo = datetime.combine(start, time.min, zone).astimezone(UTC)
    hi = datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(UTC)

    def lines() -> Select[tuple[OrderItem, Order]]:
        return (
            select(OrderItem, Order)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.ticket_type_id.in_(type_ids),
                Order.status.in_(_SOLD),
                Order.confirmed_at >= lo,
                Order.confirmed_at < hi,
            )
        )

    rows = (await session.execute(lines())).tuples().all() if type_ids else []
    bps = get_settings().processing_fee_bps
    gross = discounts = refunds = fees = sold_n = refunded_n = 0
    per_day: dict[date, list[int]] = {}
    per_type: dict[uuid.UUID, list[int]] = {}
    for item, order in rows:
        line_gross = item.unit_price_kzt * item.quantity
        gross += line_gross
        discounts += item.discount_kzt
        if order.status is OrderStatus.REFUNDED:
            refunds += item.line_total_kzt
            refunded_n += item.quantity
            continue
        # Sales that stand: they feed the chart, the per-type figures and the fees.
        sold_n += item.quantity
        fees += item.line_total_kzt * bps // 10_000
        day = order.confirmed_at.astimezone(zone).date() if order.confirmed_at else start
        bucket = per_day.setdefault(day, [0, 0])
        bucket[0] += item.quantity
        bucket[1] += item.line_total_kzt
        t = per_type.setdefault(item.ticket_type_id, [0, 0])
        t[0] += item.quantity
        t[1] += item.line_total_kzt
    net = gross - discounts - refunds

    # Capacity: ticket quantities, capped by the event capacity when there's no type filter.
    capacity = 0
    for event in events:
        event_types = [t for t in types if t.event_id == event.id]
        total = sum(t.quantity_total for t in event_types)
        if ticket_type_id is None and event.capacity is not None:
            total = min(total, event.capacity)
        capacity += total
    sold_now = sum(t.quantity_sold for t in types)

    status_counts: dict[tuple[uuid.UUID, TicketStatus], int] = {}
    if type_ids:
        for tt_id, status, n in (
            await session.execute(
                select(Ticket.ticket_type_id, Ticket.status, func.count(Ticket.id))
                .where(Ticket.ticket_type_id.in_(type_ids))
                .group_by(Ticket.ticket_type_id, Ticket.status)
            )
        ).tuples():
            status_counts[(tt_id, status)] = n
    checked_in = sum(n for (_, s), n in status_counts.items() if s is TicketStatus.CHECKED_IN)
    issued = checked_in + sum(n for (_, s), n in status_counts.items() if s is TicketStatus.VALID)

    return AnalyticsRead(
        filters=AnalyticsFilters(
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            date_from=start,
            date_to=end,
            timezone=zone_name,
        ),
        capacity=CapacityFigures(
            capacity=capacity,
            sold=sold_now,
            remaining=max(capacity - sold_now, 0),
            percent_sold=_percent(sold_now, capacity),
        ),
        revenue=RevenueFigures(
            tickets_sold=sold_n,
            tickets_refunded=refunded_n,
            gross_kzt=gross,
            discounts_kzt=discounts,
            refunds_kzt=refunds,
            net_kzt=net,
            processing_fees_kzt=fees,
            estimated_payout_kzt=net - fees,
        ),
        sales_over_time=[
            DayPoint(
                date=start + timedelta(days=i),
                tickets=per_day.get(start + timedelta(days=i), [0, 0])[0],
                revenue_kzt=per_day.get(start + timedelta(days=i), [0, 0])[1],
            )
            for i in range((end - start).days + 1)
        ],
        by_ticket_type=[
            TicketTypeFigures(
                ticket_type_id=t.id,
                event_id=t.event_id,
                name=t.name,
                price_kzt=t.price_kzt,
                capacity=t.quantity_total,
                sold=t.quantity_sold,
                tickets_in_range=per_type.get(t.id, [0, 0])[0],
                revenue_kzt=per_type.get(t.id, [0, 0])[1],
                checked_in=status_counts.get((t.id, TicketStatus.CHECKED_IN), 0),
            )
            for t in types
        ],
        campaigns=await _campaigns(session, event_ids, type_ids, lo, hi) if type_ids else [],
        attendance=AttendanceFigures(
            issued=issued,
            checked_in=checked_in,
            absent=issued - checked_in,
            percent_checked_in=_percent(checked_in, issued),
        ),
    )


async def _campaigns(
    session: AsyncSession,
    event_ids: list[uuid.UUID],
    type_ids: list[uuid.UUID],
    lo: datetime,
    hi: datetime,
) -> list[CampaignFigures]:
    """SRS 4.15: redemptions, tickets attributed to each campaign, and resulting revenue."""
    campaigns = list(
        await session.scalars(
            select(PromotionalCampaign)
            .where(PromotionalCampaign.event_id.in_(event_ids))
            .order_by(PromotionalCampaign.created_at)
        )
    )
    if not campaigns:
        return []
    ids = [c.id for c in campaigns]
    totals = {
        row.campaign_id: row
        for row in (
            await session.execute(
                select(
                    Order.campaign_id,
                    func.count(func.distinct(Order.id)).label("orders"),
                    func.coalesce(func.sum(OrderItem.quantity), 0).label("tickets"),
                    func.coalesce(func.sum(OrderItem.unit_price_kzt * OrderItem.quantity), 0).label(
                        "gross"
                    ),
                    func.coalesce(func.sum(OrderItem.discount_kzt), 0).label("discount"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Order.status == OrderStatus.REFUNDED, 0),
                                else_=OrderItem.line_total_kzt,
                            )
                        ),
                        0,
                    ).label("net"),
                )
                .join(OrderItem, OrderItem.order_id == Order.id)
                .where(
                    Order.campaign_id.in_(ids),
                    Order.status.in_(_SOLD),
                    Order.confirmed_at >= lo,
                    Order.confirmed_at < hi,
                    OrderItem.ticket_type_id.in_(type_ids),
                )
                .group_by(Order.campaign_id)
            )
        ).all()
    }
    redemptions = dict(
        (
            await session.execute(
                select(PromoRedemption.campaign_id, func.count(PromoRedemption.id))
                .where(
                    PromoRedemption.campaign_id.in_(ids),
                    PromoRedemption.redeemed_at >= lo,
                    PromoRedemption.redeemed_at < hi,
                )
                .group_by(PromoRedemption.campaign_id)
            )
        )
        .tuples()
        .all()
    )
    codes = dict(
        (
            await session.execute(
                select(PromoCode.campaign_id, PromoCode.code).where(PromoCode.campaign_id.in_(ids))
            )
        )
        .tuples()
        .all()
    )
    out = []
    for c in campaigns:
        row = totals.get(c.id)
        out.append(
            CampaignFigures(
                campaign_id=c.id,
                name=c.name,
                code=codes.get(c.id),
                redemptions=redemptions.get(c.id, 0),
                orders=row.orders if row else 0,
                tickets=row.tickets if row else 0,
                gross_kzt=row.gross if row else 0,
                discount_kzt=row.discount if row else 0,
                net_kzt=row.net if row else 0,
            )
        )
    return out
