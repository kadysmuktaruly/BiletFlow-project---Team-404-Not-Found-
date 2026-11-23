"""The Platform Admin portal (SRS 4.12). Platform Admins only; every action is audited."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.enums import (
    ActivationStatus,
    DiscountType,
    EventReportReason,
    EventReportStatus,
    EventStatus,
    EventVisibility,
    OrderStatus,
    PaymentPurpose,
    PaymentStatus,
    UserRole,
)
from app.schemas.promo import CampaignReport, EffectiveStatus


class SuspendRequest(BaseModel):
    # Kept in the audit log; required so every suspension can be explained later.
    reason: str = Field(min_length=3, max_length=2000)


class AdminUser(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_email_verified: bool
    is_suspended: bool
    suspended_at: datetime | None
    created_at: datetime


class AdminEvent(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    status: EventStatus
    visibility: EventVisibility
    is_suspended: bool
    organizer_name: str
    organizer_email: str
    starts_at: datetime
    paid_sales: ActivationStatus | None
    open_reports: int
    created_at: datetime


class AdminOrder(BaseModel):
    id: uuid.UUID
    reference: str
    status: OrderStatus
    event_id: uuid.UUID
    event_title: str
    buyer_email: str
    total_kzt: int
    refunded_kzt: int
    created_at: datetime


class AdminPayment(BaseModel):
    id: uuid.UUID
    purpose: PaymentPurpose
    status: PaymentStatus
    amount_kzt: int
    user_email: str
    event_title: str | None
    order_reference: str | None
    provider_reference: str | None
    failure_reason: str | None
    is_simulated: bool
    demo: Literal[True] = True
    created_at: datetime


class AdminActivation(BaseModel):
    """SRS 4.12 "Inspect paid-sales activation records"."""

    event_id: uuid.UUID
    event_title: str
    organizer_name: str
    status: ActivationStatus
    has_paid_ticket_type: bool
    identity_verified: bool
    payout_account_connected: bool
    activation_fee_paid: bool
    terms_accepted: bool
    activation_fee_kzt: int
    activated_at: datetime | None
    suspended_at: datetime | None
    suspended_reason: str | None
    updated_at: datetime


class AdminReport(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    event_slug: str
    event_suspended: bool
    reporter_email: str
    reason: EventReportReason
    details: str | None
    status: EventReportStatus
    created_at: datetime
    reviewed_at: datetime | None
    review_note: str | None


class ReportReview(BaseModel):
    # `dismiss`: nothing wrong. `suspend_event`: suspend the event (stops all sales now).
    action: Literal["dismiss", "suspend_event"]
    note: str | None = Field(default=None, max_length=2000)


class ReportCreate(BaseModel):
    reason: EventReportReason
    details: str | None = Field(default=None, max_length=2000)


class ReportCreated(BaseModel):
    id: uuid.UUID
    status: EventReportStatus


class SettingsRead(BaseModel):
    activation_fee_kzt: int
    # False when nobody has changed it yet and the environment default applies.
    customized: bool
    updated_at: datetime | None


class SettingsUpdate(BaseModel):
    activation_fee_kzt: int = Field(ge=0, le=100_000_000)


class AdminSummary(BaseModel):
    users: int
    suspended_users: int
    events_published: int
    suspended_events: int
    orders_confirmed: int
    payments_failed: int
    refunds: int
    open_reports: int
    open_support_cases: int
    paid_sales_suspended: int


class AdminUserList(BaseModel):
    items: list[AdminUser]
    # True when there were more matches than shown; narrow the search.
    truncated: bool


class AdminEventList(BaseModel):
    items: list[AdminEvent]
    # True when there were more matches than shown; narrow the search.
    truncated: bool


class AdminOrderList(BaseModel):
    items: list[AdminOrder]
    # True when there were more matches than shown; narrow the search.
    truncated: bool


class AdminPromotion(BaseModel):
    """SRS 4.12 "Review ... promotional-code activity": one campaign and its code, with the
    same exact sales report the organizer sees (SRS 4.14). DEMO figures."""

    campaign_id: uuid.UUID
    campaign_name: str
    event_id: uuid.UUID
    event_title: str
    organizer_email: str
    code: str
    status: EffectiveStatus
    discount_type: DiscountType
    discount_percent: int | None
    discount_kzt: int | None
    max_redemptions: int | None
    # Pending checkouts hold a redemption too, so this can be above report.redemptions.
    redeemed_count: int
    report: CampaignReport
    demo: Literal[True] = True
    created_at: datetime
    disabled_at: datetime | None


class AdminPromotionList(BaseModel):
    items: list[AdminPromotion]
    # True when there were more matches than shown; narrow the search.
    truncated: bool


class AdminPaymentList(BaseModel):
    items: list[AdminPayment]
    # True when there were more matches than shown; narrow the search.
    truncated: bool


class AdminActivationList(BaseModel):
    items: list[AdminActivation]
    # True when there were more matches than shown; narrow the search.
    truncated: bool


class AdminReportList(BaseModel):
    items: list[AdminReport]
    # True when there were more matches than shown; narrow the search.
    truncated: bool
