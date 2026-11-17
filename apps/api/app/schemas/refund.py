"""Orders as organizers see them, refunds and registration cancellations (SRS 4.9).

Every refund is simulated (DEMO): no real money moves, and every schema says so.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.enums import OrderStatus, RefundStatus


class RefundRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class CancelRegistrationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class RefundRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    status: RefundStatus
    amount_kzt: int
    currency: str
    reason: str | None
    is_simulated: bool
    # Always true (SRS 4.6): demonstration refunds are never presented as real transactions.
    demo: Literal[True] = True
    provider_reference: str | None
    created_at: datetime
    succeeded_at: datetime | None


class OrganizerOrderRead(BaseModel):
    """One order of the organizer's event. Buyer contact details are shown to the organizer
    because they need them to run the event (SRS 4.4 attendee list, 4.9 refunds)."""

    id: uuid.UUID
    reference: str
    status: OrderStatus
    buyer_name: str
    buyer_email: str
    tickets: int
    subtotal_kzt: int
    discount_kzt: int
    total_kzt: int
    refunded_kzt: int
    processing_fee_kzt: int
    promo_code: str | None
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    # What the organizer may do with it now.
    can_refund: bool
    can_cancel: bool


class OrganizerOrderList(BaseModel):
    orders: list[OrganizerOrderRead]
    truncated: bool


class RefundResult(BaseModel):
    order: OrganizerOrderRead
    refund: RefundRead
    # True when this response replays an earlier request with the same Idempotency-Key.
    replayed: bool
