"""Ticket types (SRS 4.3): free or paid, quantity, sales window, per-order limit, hidden."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _TicketTypeFields(BaseModel):
    """Sales-window times without a UTC offset are read in the event's time zone."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    # Whole KZT. 0 means free.
    price_kzt: int = Field(ge=0, le=100_000_000)
    quantity_total: int = Field(ge=0, le=1_000_000)
    max_per_order: int = Field(default=10, ge=1, le=100)
    sales_start_at: datetime | None = None
    sales_end_at: datetime | None = None
    is_hidden: bool = False


class TicketTypeCreate(_TicketTypeFields):
    @model_validator(mode="after")
    def _window(self) -> "TicketTypeCreate":
        if (
            self.sales_start_at
            and self.sales_end_at
            and self.sales_start_at.tzinfo is not None
            and self.sales_end_at.tzinfo is not None
            and self.sales_end_at <= self.sales_start_at
        ):
            raise ValueError("Sales must end after they start.")
        return self


class TicketTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price_kzt: int | None = Field(default=None, ge=0, le=100_000_000)
    quantity_total: int | None = Field(default=None, ge=0, le=1_000_000)
    max_per_order: int | None = Field(default=None, ge=1, le=100)
    sales_start_at: datetime | None = None
    sales_end_at: datetime | None = None
    is_hidden: bool | None = None


class TicketTypeRead(BaseModel):
    """The organizer's view, with the SRS 4.3 counts: available, reserved, sold, refunded,
    checked in."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    name: str
    description: str | None
    price_kzt: int
    is_free: bool
    quantity_total: int
    quantity_sold: int
    quantity_reserved: int
    quantity_available: int
    quantity_refunded: int = 0
    quantity_checked_in: int = 0
    max_per_order: int
    sales_start_at: datetime | None
    sales_end_at: datetime | None
    is_hidden: bool


class PublicTicketTypeRead(BaseModel):
    """What attendees see. No sold/reserved counts, only whether any are left."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price_kzt: int
    is_free: bool
    quantity_available: int
    max_per_order: int
    sales_start_at: datetime | None
    sales_end_at: datetime | None
    on_sale: bool
