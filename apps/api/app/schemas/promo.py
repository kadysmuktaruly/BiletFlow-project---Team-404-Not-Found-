"""Promotional campaigns, promo codes and Campaign QR links (SRS 4.14).

No request here carries a price or a discount amount the server would trust. The organizer
configures a discount once; attendees only ever send a code (or a campaign token), and the
server computes what it's worth (SRS 4.14, SRS 7).
"""

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.enums import DiscountType
from app.schemas.order import OrderItemInput

# Letters, digits and dashes, so a code reads aloud and types on a phone keyboard.
CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9-]{2,39}$"

EffectiveStatus = Literal["active", "scheduled", "expired", "exhausted", "disabled"]

# Why a code can't be used right now. Clients translate these.
PromoRejection = Literal[
    "promo_not_found",
    "promo_disabled",
    "promo_not_started",
    "promo_expired",
    "promo_exhausted",
    "promo_not_applicable",
]


class _DiscountShape(BaseModel):
    discount_type: DiscountType
    discount_percent: int | None = Field(default=None, ge=1, le=100)
    discount_kzt: int | None = Field(default=None, ge=1, le=100_000_000)

    @model_validator(mode="after")
    def _one_discount(self) -> Self:
        if self.discount_type is DiscountType.PERCENTAGE:
            if self.discount_percent is None or self.discount_kzt is not None:
                raise ValueError("A percentage discount needs discount_percent only.")
        elif self.discount_kzt is None or self.discount_percent is not None:
            raise ValueError("A fixed discount needs discount_kzt only.")
        return self


class CampaignCreate(_DiscountShape):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    # Leave empty to have the server generate one.
    code: str | None = Field(default=None, pattern=CODE_PATTERN)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1, le=1_000_000)
    # Empty means every ticket type on the event.
    ticket_type_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not be before starts_at.")
        return self


class CampaignUpdate(BaseModel):
    """Name, description, validity dates and the redemption limit. The discount and the
    eligible ticket types are fixed once created, so earlier orders stay explainable."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1, le=1_000_000)


class CampaignReport(BaseModel):
    """SRS 4.14: "exact redemptions, orders, tickets sold, gross revenue, discount amount,
    and net revenue for each campaign". Counted over confirmed (and later refunded) orders;
    `net_revenue_kzt` subtracts refunds. DEMO figures: no real money moved."""

    redemptions: int
    orders: int
    tickets_sold: int
    gross_revenue_kzt: int
    discount_kzt: int
    net_revenue_kzt: int


class CampaignRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    name: str
    description: str | None
    discount_type: DiscountType
    discount_percent: int | None
    discount_kzt: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    code: str
    max_redemptions: int | None
    # Includes orders still awaiting payment (they hold a redemption until they expire).
    redeemed_count: int
    ticket_type_ids: list[uuid.UUID]
    status: EffectiveStatus
    # The Campaign QR encodes this link and nothing else: an opaque token, no discount.
    campaign_url: str
    qr_token: str
    created_at: datetime
    disabled_at: datetime | None
    report: CampaignReport


class PromoValidateRequest(BaseModel):
    event_id: uuid.UUID
    code: str = Field(min_length=1, max_length=40)
    items: list[OrderItemInput] = Field(min_length=1, max_length=20)


class PromoLine(BaseModel):
    ticket_type_id: uuid.UUID
    quantity: int
    line_subtotal_kzt: int
    discount_kzt: int
    line_total_kzt: int


class PromoQuote(BaseModel):
    """What the code is worth for these items. A preview: checkout recomputes it."""

    code: str
    campaign_name: str
    discount_type: DiscountType
    discount_percent: int | None
    discount_kzt: int
    subtotal_kzt: int
    total_kzt: int
    lines: list[PromoLine]


class CampaignResolution(BaseModel):
    """Where a Campaign QR leads. The code comes back only after the server has checked the
    campaign can be used; otherwise `rejection` says why and the page opens without it."""

    event_id: uuid.UUID
    event_slug: str
    code: str | None
    campaign_name: str
    rejection: PromoRejection | None = None
