"""The signed-in user, as the API shows them to themselves."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import UserRole
from app.i18n import Locale


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: UserRole
    locale: Locale
    is_email_verified: bool
    created_at: datetime


class UserUpdate(BaseModel):
    """Fields a user may change about themselves. Role and email are not among them."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    locale: Locale | None = None
