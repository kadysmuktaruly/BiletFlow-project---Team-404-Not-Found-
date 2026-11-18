"""Support cases (SRS 4.13). No attachments in the MVP (SRS §12 decision)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.enums import SupportCaseStatus, SupportCategory

CaseKind = Literal["attendee", "organizer"]
# How the signed-in user relates to a case: they opened it, or they handle it.
ViewerRole = Literal["requester", "staff"]


class CaseCreate(BaseModel):
    """`attendee`: about an event, order or ticket, answered by the event's organizer team.
    `organizer`: an organizer asking the platform (account, activation, payment, technical).
    The server derives the event from the order or ticket and checks they're yours."""

    kind: CaseKind = "attendee"
    category: SupportCategory
    subject: str = Field(min_length=3, max_length=300)
    message: str = Field(min_length=1, max_length=5000)
    event_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    ticket_id: uuid.UUID | None = None


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    # Staff only: a note the requester never sees.
    internal: bool = False


class CaseUpdate(BaseModel):
    status: SupportCaseStatus | None = None
    # Must be someone who handles this case; null to unassign.
    assigned_to_user_id: uuid.UUID | None = None


class Person(BaseModel):
    id: uuid.UUID
    full_name: str


class MessageRead(BaseModel):
    id: uuid.UUID
    author: Person
    # True when the author is on the handling side (organizer team or platform).
    from_staff: bool
    body: str
    internal: bool
    created_at: datetime


class CaseContext(BaseModel):
    event_id: uuid.UUID | None
    event_title: str | None
    event_slug: str | None
    order_id: uuid.UUID | None
    order_reference: str | None
    ticket_id: uuid.UUID | None
    ticket_number: str | None


class CaseSummary(BaseModel):
    id: uuid.UUID
    reference: str
    kind: CaseKind
    category: SupportCategory
    status: SupportCaseStatus
    subject: str
    requester: Person
    assigned_to: Person | None
    context: CaseContext
    viewer_role: ViewerRole
    created_at: datetime
    last_message_at: datetime | None
    resolved_at: datetime | None


class CaseRead(CaseSummary):
    messages: list[MessageRead]
    # What the signed-in user may do.
    can_manage: bool
    assignees: list[Person]
