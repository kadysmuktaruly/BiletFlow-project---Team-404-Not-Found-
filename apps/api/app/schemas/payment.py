"""DEMO payments (SRS 4.6). Every payment here is simulated, and every schema says so."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Header
from pydantic import BaseModel, Field

from app.enums import ActivationStatus, PaymentPurpose, PaymentStatus
from app.schemas.order import OrderRead

# Retries with the same key return the original result instead of charging again.
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9_\-:.]+$",
        description="A unique value per payment attempt, e.g. a UUID. Reuse it to retry safely.",
    ),
]


class SimulatedPaymentRequest(BaseModel):
    """The DEMO checkout screen lets the attendee choose what the simulated provider does."""

    outcome: Literal["succeed", "fail"]


class PaymentRead(BaseModel):
    id: uuid.UUID
    purpose: PaymentPurpose
    status: PaymentStatus
    amount_kzt: int
    currency: str
    provider: str
    provider_reference: str | None
    card_brand: str | None
    card_last4: str | None
    failure_reason: str | None
    is_simulated: bool
    # Always true. SRS 4.6: demonstration payments are never presented as real transactions.
    demo: Literal[True] = True
    created_at: datetime
    succeeded_at: datetime | None


class OrderPaymentResult(BaseModel):
    payment: PaymentRead
    order: OrderRead
    # True when this response replays an earlier request with the same Idempotency-Key.
    replayed: bool


class ActivationStep(BaseModel):
    done: bool


class ActivationRead(BaseModel):
    """SRS 3.2 / 4.5: the paid-sales checklist for one event."""

    event_id: uuid.UUID
    status: ActivationStatus
    # Paid checkout is open only when this is true.
    paid_sales_enabled: bool
    has_paid_ticket_type: bool
    identity_verified: bool
    payout_account_connected: bool
    activation_fee_paid: bool
    terms_accepted: bool
    # From ACTIVATION_FEE_KZT. Non-refundable (docs/decisions.md).
    activation_fee_kzt: int
    fee_refundable: Literal[False] = False
    activation_payment: PaymentRead | None
    activated_at: datetime | None
    suspended_at: datetime | None
    demo: Literal[True] = True


class ConfirmRequest(BaseModel):
    """For checklist steps that are a simple confirmation."""

    confirm: Literal[True] = Field(description="Must be true.")
