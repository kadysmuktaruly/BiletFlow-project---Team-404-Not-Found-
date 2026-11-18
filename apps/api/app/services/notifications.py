"""Notification records (SRS 4.10). Each email a user receives gets a row here."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NotificationChannel, NotificationType
from app.models import Notification
from app.services.mail import OutgoingEmail


async def record_email(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: NotificationType,
    msg: OutgoingEmail,
    event_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    ticket_id: uuid.UUID | None = None,
) -> Notification:
    """Add a pending email notification to the session. The caller commits, then schedules
    `app.services.mail.deliver(msg, notification.id)`, which marks it sent or failed."""
    notification = Notification(
        user_id=user_id,
        type=type,
        channel=NotificationChannel.EMAIL,
        subject=msg.subject[:300],
        body=msg.text,
        event_id=event_id,
        order_id=order_id,
        ticket_id=ticket_id,
    )
    session.add(notification)
    await session.flush()
    return notification
