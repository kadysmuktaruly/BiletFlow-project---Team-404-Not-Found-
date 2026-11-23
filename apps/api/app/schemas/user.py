"""The signed-in user, as the API shows them to themselves."""

import uuid
from datetime import datetime
from typing import Literal

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
    """Fields a user may change about themselves. Email is not among them, and the role
    changes only through `PUT /me/role`."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    locale: Locale | None = None


class RoleChange(BaseModel):
    """Self-service roles only: platform admins are appointed, and event admins come from
    StaffAssignment."""

    role: Literal["attendee", "organizer"]
