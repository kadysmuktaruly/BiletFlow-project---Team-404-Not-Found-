"""Event staff (SRS 4.8, 2.3): people an organizer authorizes to check attendees in."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

from app.enums import StaffRole


class StaffAssign(BaseModel):
    email: EmailStr
    # Event admins can also undo a check-in; check-in staff can only scan.
    role: Literal["event_admin", "check_in_staff"] = "event_admin"


class StaffRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: StaffRole
    assigned_at: datetime
