"""Basic organizer analytics (SRS 4.15). Every figure comes from BiletFlow's own order,
ticket, campaign, refund and check-in records; nothing is asked of attendees. Money is
whole KZT and DEMO: no real money moved."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel


class AnalyticsFilters(BaseModel):
    event_id: uuid.UUID | None
    ticket_type_id: uuid.UUID | None
    date_from: date
    date_to: date
    # Days are cut in this zone: the event's own, or Asia/Almaty across several events.
    timezone: str


class CapacityFigures(BaseModel):
    """Current state, not limited to the date range."""

    capacity: int
    sold: int
    remaining: int
    percent_sold: float


class RevenueFigures(BaseModel):
    """Orders confirmed in the date range (refunded ones included as refunds)."""

    tickets_sold: int
    tickets_refunded: int
    gross_kzt: int
    discounts_kzt: int
    refunds_kzt: int
    net_kzt: int
    # SRS 4.6 / 3.3: processing charges come out of the organizer's payout.
    processing_fees_kzt: int
    estimated_payout_kzt: int
    demo: Literal[True] = True


class DayPoint(BaseModel):
    date: date
    tickets: int
    revenue_kzt: int


class TicketTypeFigures(BaseModel):
    ticket_type_id: uuid.UUID
    event_id: uuid.UUID
    name: str
    price_kzt: int
    capacity: int
    sold: int
    tickets_in_range: int
    revenue_kzt: int
    checked_in: int


class CampaignFigures(BaseModel):
    campaign_id: uuid.UUID
    name: str
    code: str | None
    redemptions: int
    orders: int
    tickets: int
    gross_kzt: int
    discount_kzt: int
    net_kzt: int


class AttendanceFigures(BaseModel):
    """Current state. `absent` = issued tickets not (yet) checked in."""

    issued: int
    checked_in: int
    absent: int
    percent_checked_in: float


class AnalyticsRead(BaseModel):
    filters: AnalyticsFilters
    capacity: CapacityFigures
    revenue: RevenueFigures
    sales_over_time: list[DayPoint]
    by_ticket_type: list[TicketTypeFigures]
    campaigns: list[CampaignFigures]
    attendance: AttendanceFigures
