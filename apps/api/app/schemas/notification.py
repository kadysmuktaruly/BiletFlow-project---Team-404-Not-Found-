"""The in-app notification inbox (SRS 4.10, 4.13)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.enums import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    subject: str
    body: str
    # Web path without the locale prefix, e.g. "/orders/<id>"; null if it leads nowhere.
    action_path: str | None
    event_id: uuid.UUID | None
    order_id: uuid.UUID | None
    created_at: datetime
    read_at: datetime | None


class NotificationList(BaseModel):
    items: list[NotificationRead]
    unread_count: int


class UnreadCount(BaseModel):
    unread_count: int
