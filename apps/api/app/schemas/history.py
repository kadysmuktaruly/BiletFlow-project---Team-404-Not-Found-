"""Organizer event history (SRS 4.16): the activity timeline."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TimelineEntry(BaseModel):
    """SRS 4.16: "timestamp, acting user, action type, affected entity, and short
    description". Read from the append-only audit log."""

    id: uuid.UUID
    occurred_at: datetime
    actor_name: str | None
    action: str
    # The part of `action` before the dot, e.g. "order", "promo", "ticket".
    category: str
    entity_type: str
    entity_id: uuid.UUID | None
    description: str


class Timeline(BaseModel):
    entries: list[TimelineEntry]
    # Every category this event's history has, for the activity filter.
    categories: list[str]
    truncated: bool
