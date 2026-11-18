"""Notifications (SRS 4.10, 4.13): the one interface every feature calls to tell a user
something.

    outbound = await notify(session, user, Message(
        type=NotificationType.REFUND_COMPLETED,
        template="refund_completed",          # key in app.i18n.emails
        params={"event": ..., "reference": ..., "amount": ...},
        action_path=f"/orders/{order.id}",    # where the in-app item leads (no locale prefix)
        order_id=order.id,
    ))

`notify` renders the template in the recipient's language and writes up to two
`Notification` rows in the caller's transaction:

* **email**: `pending` until `app.services.mail.deliver` sends it after commit (the caller
  passes the returned `Outbound` to `schedule`), then `sent` or `failed`.
* **in-app**: available at once in `GET /me/notifications`, unread until the user reads it.

Both are built from the same template, so the inbox and the email always say the same thing.
`{name}` is filled from the recipient; don't pass it.
"""

import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NotificationChannel, NotificationStatus, NotificationType
from app.errors import AppError
from app.i18n import normalize_locale
from app.i18n.emails import EMAILS
from app.models import Notification, User
from app.services.mail import Attachment, Outbound, OutgoingEmail, render


@dataclass(frozen=True)
class Message:
    type: NotificationType
    template: str
    params: dict[str, Any] = field(default_factory=dict)
    action_path: str | None = None
    event_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    ticket_id: uuid.UUID | None = None
    attachments: Sequence[Attachment] = ()
    extra_text: str = ""
    extra_html: str = ""
    email: bool = True
    in_app: bool = True


def web_url(locale: str, path: str) -> str:
    from app.config import get_settings

    return f"{get_settings().public_base_url.rstrip('/')}/{locale}{path}"


def in_app_text(template: str, locale: str | None, params: dict[str, Any]) -> tuple[str, str]:
    """Subject and a short plain-text body for the inbox, from the email template."""
    tpl = EMAILS[template][normalize_locale(locale)]
    subject = tpl["subject"].format(**params)
    body = " ".join(p.format(**params) for p in tpl.get("paragraphs", []))
    return subject[:300], body


async def notify(session: AsyncSession, user: User, message: Message) -> Outbound:
    locale = normalize_locale(user.locale)
    params = {"name": user.full_name, **message.params}
    context = {
        "event_id": message.event_id,
        "order_id": message.order_id,
        "ticket_id": message.ticket_id,
    }
    outbound: Outbound = []
    if message.in_app:
        subject, body = in_app_text(message.template, locale, params)
        session.add(
            Notification(
                user_id=user.id,
                type=message.type,
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.SENT,
                subject=subject,
                body=body,
                action_path=message.action_path,
                sent_at=datetime.now(UTC),
                **context,
            )
        )
    if message.email:
        msg = render(
            message.template,
            locale,
            to=user.email,
            action_url=web_url(locale, message.action_path) if message.action_path else None,
            extra_text=message.extra_text,
            extra_html=message.extra_html,
            attachments=list(message.attachments),
            **params,
        )
        notification = await record_email(
            session, user_id=user.id, type=message.type, msg=msg, **context
        )
        notification.action_path = message.action_path
        outbound.append((msg, notification.id))
    await session.flush()
    return outbound


async def notify_users(
    session: AsyncSession, users: Iterable[User], build: Callable[[User], Message]
) -> Outbound:
    """Notify each user once (duplicates are skipped), building a message per user."""
    outbound: Outbound = []
    seen: set[uuid.UUID] = set()
    for user in users:
        if user.id in seen:
            continue
        seen.add(user.id)
        outbound += await notify(session, user, build(user))
    return outbound


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
    `app.services.mail.deliver(msg, notification.id)`, which marks it sent or failed. Used
    directly only for account emails that have no in-app copy (e.g. verification)."""
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


# --- the in-app inbox ---------------------------------------------------------------------


def _inbox(user: User) -> Select[tuple[Notification]]:
    return select(Notification).where(
        Notification.user_id == user.id, Notification.channel == NotificationChannel.IN_APP
    )


async def list_in_app(
    session: AsyncSession, user: User, *, unread_only: bool, limit: int
) -> tuple[list[Notification], int]:
    query = _inbox(user)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    items = list(
        await session.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id).limit(limit)
        )
    )
    return items, await unread_count(session, user)


async def unread_count(session: AsyncSession, user: User) -> int:
    count = await session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.channel == NotificationChannel.IN_APP,
            Notification.read_at.is_(None),
        )
    )
    return count or 0


async def mark_read(session: AsyncSession, user: User, notification_id: uuid.UUID) -> Notification:
    notification = await session.scalar(_inbox(user).where(Notification.id == notification_id))
    if notification is None:
        raise AppError(404, "notification_not_found", "Notification not found.")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        notification.status = NotificationStatus.READ
        await session.commit()
    return notification


async def mark_all_read(session: AsyncSession, user: User) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.channel == NotificationChannel.IN_APP,
            Notification.read_at.is_(None),
        )
        .values(read_at=now, status=NotificationStatus.READ)
    )
    await session.commit()
