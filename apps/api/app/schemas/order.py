"""Orders and tickets as attendees see them (SRS 4.4, 4.6, 4.7).

Attendees never see `processing_fee_kzt`: processing charges come out of the organizer's
payout, so the attendee's total is the ticket price minus any discount (docs/decisions.md).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.enums import OrderStatus, TicketStatus


class OrderItemInput(BaseModel):
    ticket_type_id: uuid.UUID
    quantity: int = Field(ge=1, le=100)


class AttendeeInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)


class OrderCreate(BaseModel):
    """Only ids and quantities. Every price and total is computed on the server (SRS 7)."""

    event_id: uuid.UUID
    items: list[OrderItemInput] = Field(min_length=1, max_length=20)
    # One per ticket, in item order. Leave empty to issue every ticket in the buyer's name.
    attendees: list[AttendeeInput] = Field(default_factory=list, max_length=100)


class EventSummary(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    venue_name: str | None
    venue_address: str | None


class OrderItemRead(BaseModel):
    id: uuid.UUID
    ticket_type_id: uuid.UUID
    ticket_type_name: str
    quantity: int
    unit_price_kzt: int
    discount_kzt: int
    line_total_kzt: int


class TicketRead(BaseModel):
    id: uuid.UUID
    ticket_number: str
    status: TicketStatus
    ticket_type_id: uuid.UUID
    ticket_type_name: str
    attendee_name: str
    attendee_email: str | None
    seat_section: str | None = None
    seat_row: str | None = None
    seat_number: str | None = None
    # The signed admission token encoded in the QR code. It identifies the ticket only;
    # status is always checked live at the door.
    qr_payload: str
    issued_at: datetime | None
    checked_in_at: datetime | None


class MyTicketRead(TicketRead):
    order_id: uuid.UUID
    order_reference: str
    event: EventSummary


class OrderRead(BaseModel):
    id: uuid.UUID
    reference: str
    status: OrderStatus
    event: EventSummary
    subtotal_kzt: int
    discount_kzt: int
    total_kzt: int
    currency: str
    # True while the order waits for a (DEMO) payment before `expires_at`.
    payment_required: bool
    expires_at: datetime | None
    confirmed_at: datetime | None
    created_at: datetime
    items: list[OrderItemRead]
    tickets: list[TicketRead]
