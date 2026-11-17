"""Check-in (SRS 4.8): what the Event Admin scanner app sees."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.enums import CheckInMethod, EventStatus, TicketStatus

StaffAccessRole = Literal["owner", "event_admin", "check_in_staff"]


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
    role: StaffAccessRole
    # Event admins and owners can undo a check-in; check-in staff can't.
    can_undo: bool


# SRS 4.8: "Display a clear valid, invalid, cancelled, refunded, or already-used result."
ScanOutcome = Literal["valid", "invalid", "cancelled", "refunded", "already_used"]

# Why a scan was `invalid`. Clients translate these; they never show raw text.
InvalidReason = Literal[
    # Not a BiletFlow admission token, or its signature doesn't match.
    "unrecognized",
    # A Campaign QR (BFC1.) or campaign link: a promotion, never permission to enter.
    "campaign_qr_not_admission",
    # An authentic ticket, but for a different event.
    "wrong_event",
]


class ScanRequest(BaseModel):
    payload: str = Field(
        min_length=1,
        max_length=2048,
        description="The raw text the camera read from the QR code.",
    )
    device_label: str | None = Field(
        default=None, max_length=120, description="Optional name of the scanning device."
    )


class ManualCheckInRequest(BaseModel):
    device_label: str | None = Field(default=None, max_length=120)


class UndoCheckInRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class CheckInTicket(BaseModel):
    """The ticket behind a scan or search result. No price or payment data."""

    id: uuid.UUID
    ticket_number: str
    status: TicketStatus
    attendee_name: str
    ticket_type_name: str
    checked_in_at: datetime | None


class CheckInStats(BaseModel):
    """SRS 4.8: "View the total number of registered and checked-in attendees."

    `registered` counts tickets that can still be used or already were (valid or checked
    in). Cancelled and refunded tickets aren't attendees any more.
    """

    registered: int
    checked_in: int


class ScanResult(BaseModel):
    result: ScanOutcome
    reason: InvalidReason | None = Field(
        default=None, description="Set only when `result` is `invalid`."
    )
    # Present whenever the token named a ticket of this event.
    ticket: CheckInTicket | None = None
    method: CheckInMethod | None = Field(
        default=None, description="How this check-in was recorded, when `result` is `valid`."
    )
    stats: CheckInStats


class UndoResult(BaseModel):
    ticket: CheckInTicket
    stats: CheckInStats


class AttendeeSearchResult(BaseModel):
    tickets: list[CheckInTicket]
    stats: CheckInStats


class OrganizerAttendee(CheckInTicket):
    """A row of the organizer's attendee list (SRS 4.4: "The organizer shall see the
    registration in the attendee list")."""

    attendee_email: str | None
    order_id: uuid.UUID
    order_reference: str
    issued_at: datetime | None


class OrganizerAttendeeList(BaseModel):
    attendees: list[OrganizerAttendee]
    stats: CheckInStats
    # True when there were more matches than `limit`; narrow the search to see the rest.
    truncated: bool
