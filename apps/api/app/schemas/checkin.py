"""Check-in (SRS 4.8): what the Event Admin scanner app sees."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.enums import EventStatus


class CheckInEvent(BaseModel):
    """An event the signed-in user may check attendees in at."""

    id: uuid.UUID
    title: str
    status: EventStatus
    starts_at: datetime
    ends_at: datetime
    timezone: str
    venue_name: str | None
    # How the user is authorized: they organize it, or they're assigned staff.
    role: Literal["owner", "event_admin", "check_in_staff"]
    # Event admins and owners can undo a check-in; check-in staff can't.
    can_undo: bool
