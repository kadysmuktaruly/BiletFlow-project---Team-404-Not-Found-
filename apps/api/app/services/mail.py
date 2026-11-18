"""Transactional email (SRS 4.10): rendering, transport, and delivery bookkeeping.

Two backends, chosen by `EMAIL_BACKEND`:

* `smtp`: sends through `SMTP_HOST:SMTP_PORT`. In development that is Mailpit, so every
  message is visible at http://localhost:8025.
* `memory`: appends to an in-process outbox (`outbox()`). The test suite uses it.

Services build an `OutgoingEmail` with `render(...)` and record a `Notification` row in the
same transaction as the change that caused it. The router then schedules `deliver(...)` as a
background task, so mail goes out only after that transaction has committed, and a slow or
broken mail server never fails the request.
"""

import html
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any

import aiosmtplib

from app.config import get_settings
from app.db import SessionLocal
from app.enums import NotificationStatus
from app.i18n import Locale, normalize_locale
from app.i18n.emails import EMAILS, FOOTER
from app.models import Notification

logger = logging.getLogger(__name__)


@dataclass
class Attachment:
    filename: str
    content: bytes
    mime_type: str
    # When set, the part is attached inline and HTML can reference it as `cid:<inline_cid>`.
    inline_cid: str | None = None


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str
    attachments: list[Attachment] = field(default_factory=list)
    # Which `app.i18n.emails` template produced it; tests and logs key on this.
    template: str = ""


_outbox: list[OutgoingEmail] = []


def outbox() -> list[OutgoingEmail]:
    """Messages "sent" by the memory backend, oldest first."""
    return _outbox


def render(
    template: str,
    locale: str | None,
    *,
    to: str,
    action_url: str | None = None,
    extra_text: str = "",
    extra_html: str = "",
    attachments: list[Attachment] | None = None,
    **params: Any,
) -> OutgoingEmail:
    """Build a message from `app.i18n.emails`. `params` fill the `{placeholders}`."""
    loc: Locale = normalize_locale(locale)
    tpl = EMAILS[template][loc]
    safe = {k: html.escape(str(v)) for k, v in params.items()}

    def fmt(s: str, escape: bool) -> str:
        return s.format(**(safe if escape else params))

    subject = fmt(tpl["subject"], escape=False)
    paragraphs = tpl.get("paragraphs", [])

    text_parts = [fmt(tpl["greeting"], False), ""]
    text_parts += [fmt(p, False) for p in paragraphs]
    if extra_text:
        text_parts += ["", extra_text]
    if action_url:
        text_parts += ["", f"{fmt(tpl['action'], False)}: {action_url}"]
    if "note" in tpl:
        text_parts += ["", fmt(tpl["note"], False)]
    text_parts += ["", "—", FOOTER[loc]]

    html_parts = [f"<p>{fmt(tpl['greeting'], True)}</p>"]
    html_parts += [f"<p>{fmt(p, True)}</p>" for p in paragraphs]
    html_parts.append(extra_html)
    if action_url:
        url = html.escape(action_url, quote=True)
        html_parts.append(
            f'<p><a href="{url}" style="display:inline-block;padding:10px 18px;'
            'background:#111827;color:#ffffff;text-decoration:none;border-radius:6px">'
            f"{fmt(tpl['action'], True)}</a></p>"
            f'<p style="font-size:12px;color:#6b7280">{url}</p>'
        )
    if "note" in tpl:
        html_parts.append(f'<p style="color:#6b7280">{fmt(tpl["note"], True)}</p>')
    html_parts.append(f'<hr><p style="font-size:12px;color:#6b7280">{FOOTER[loc]}</p>')
    body = (
        '<!DOCTYPE html><html><body style="font-family:Arial,Helvetica,sans-serif;'
        f'color:#111827;max-width:600px">{"".join(html_parts)}</body></html>'
    )
    return OutgoingEmail(
        to=to,
        subject=subject,
        text="\n".join(text_parts),
        html=body,
        attachments=attachments or [],
        template=template,
    )


def _to_mime(msg: OutgoingEmail) -> EmailMessage:
    settings = get_settings()
    mime = EmailMessage()
    mime["From"] = settings.smtp_from
    mime["To"] = msg.to
    mime["Subject"] = msg.subject
    mime["Message-ID"] = make_msgid(domain="biletflow.local")
    mime.set_content(msg.text)
    mime.add_alternative(msg.html, subtype="html")
    html_part = next(p for p in mime.iter_parts() if p.get_content_type() == "text/html")
    for att in msg.attachments:
        maintype, subtype = att.mime_type.split("/", 1)
        if att.inline_cid:
            html_part.add_related(
                att.content, maintype, subtype, cid=f"<{att.inline_cid}>", filename=att.filename
            )
        else:
            mime.add_attachment(att.content, maintype, subtype, filename=att.filename)
    return mime


async def send_email(msg: OutgoingEmail) -> None:
    settings = get_settings()
    if settings.email_backend == "memory":
        _outbox.append(msg)
        return
    await aiosmtplib.send(
        _to_mime(msg), hostname=settings.smtp_host, port=settings.smtp_port, timeout=10
    )


async def deliver(msg: OutgoingEmail, notification_id: uuid.UUID | None = None) -> None:
    """Send, then record the outcome on the Notification row. Never raises."""
    status = NotificationStatus.SENT
    try:
        await send_email(msg)
    except Exception:
        logger.exception("Email delivery failed (template=%s)", msg.template)
        status = NotificationStatus.FAILED
    if notification_id is None:
        return
    try:
        async with SessionLocal() as session:
            notification = await session.get(Notification, notification_id)
            if notification is not None:
                notification.status = status
                if status is NotificationStatus.SENT:
                    notification.sent_at = datetime.now(UTC)
                await session.commit()
    except Exception:
        logger.exception("Could not record email delivery status")


# What a service hands back to its router: messages to deliver once the transaction has
# committed, each with the Notification row that tracks it (None if there is no matching
# notification type, e.g. password reset).
Outbound = list[tuple[OutgoingEmail, uuid.UUID | None]]
