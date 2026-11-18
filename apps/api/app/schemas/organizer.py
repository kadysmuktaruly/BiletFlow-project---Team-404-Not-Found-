"""Organizer profile and payout account (SRS 4.1: contact and payout information)."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.enums import PayoutAccountStatus


class OrganizerProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    contact_email: str
    contact_phone: str | None
    description: str | None
    website_url: str | None
    logo_url: str | None


class OrganizerProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=5000)
    website_url: HttpUrl | None = None
    logo_url: HttpUrl | None = None


class PayoutAccountRead(BaseModel):
    """A simulated payout account. Only the last four digits are ever stored (SRS 7)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_holder_name: str
    bank_name: str
    account_last4: str
    status: PayoutAccountStatus
    verified_at: datetime | None
    is_simulated: bool
    # Always true: this is demonstration data, never a real financial instrument (SRS 4.6).
    demo: bool = True


class PayoutAccountUpsert(BaseModel):
    account_holder_name: str = Field(min_length=1, max_length=200)
    bank_name: str = Field(min_length=1, max_length=200)
    # The client sends the last four digits only. The full number never reaches the server.
    account_last4: Annotated[str, Field(pattern=r"^\d{4}$")]
