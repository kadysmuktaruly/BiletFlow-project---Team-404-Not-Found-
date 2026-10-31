"""Order emails (SRS 4.4, 4.6, 4.10): the confirmation with every QR ticket, and the DEMO
payment-failure notice."""

import html
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import NotificationType
from app.i18n import normalize_locale
from app.i18n.emails import TICKET_LABELS
from app.models import Event, Order, Ticket, User
from app.services.mail import Attachment, Outbound, render
from app.services.notifications import record_email
from app.tickets.qr import qr_png


def format_kzt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " KZT"


def format_when(event: Event) -> str:
    local = event.starts_at.astimezone(ZoneInfo(event.timezone))
    return f"{local:%d.%m.%Y %H:%M} ({event.timezone})"


def _venue(event: Event) -> str:
    v = event.venue
    return ", ".join(p for p in (v.name, v.address_line1, v.city) if p) if v else ""


async def confirmation(session: AsyncSession, order: Order) -> Outbound:
    """Call after `confirm_order`, in the same transaction."""
    from app.services.orders import tickets_read  # avoid an import cycle

    user = await session.get_one(User, order.user_id)
    event = await session.get_one(Event, order.event_id)
    locale = normalize_locale(user.locale)
    labels = TICKET_LABELS[locale]
    tickets = list(
        await session.scalars(select(Ticket).where(Ticket.order_id == order.id).order_by(Ticket.id))
    )
    reads = await tickets_read(session, tickets)

    attachments: list[Attachment] = []
    text_blocks: list[str] = []
    html_blocks: list[str] = []
    for read in reads:
        cid = f"qr-{read.id}@biletflow"
        attachments.append(
            Attachment(
                f"ticket-{read.ticket_number}.png", qr_png(read.qr_payload), "image/png", cid
            )
        )
        text_blocks.append(
            f"{labels['ticket']} {read.ticket_number} · {labels['ticket_type']}: "
            f"{read.ticket_type_name} · {labels['attendee']}: {read.attendee_name}"
        )
        html_blocks.append(
            '<div style="border:1px solid #d1d5db;border-radius:8px;padding:16px;margin:12px 0">'
            f'<img src="cid:{cid}" width="220" height="220" '
            f'alt="QR {html.escape(read.ticket_number)}" style="display:block;background:#fff">'
            f'<p style="margin:8px 0 0;font-size:18px;font-weight:bold;letter-spacing:1px">'
            f"{html.escape(read.ticket_number)}</p>"
            f'<p style="margin:4px 0 0">{html.escape(labels["ticket_type"])}: '
            f"{html.escape(read.ticket_type_name)}<br>{html.escape(labels['attendee'])}: "
            f"{html.escape(read.attendee_name)}</p></div>"
        )
    money = (
        labels["free"]
        if order.total_kzt == 0
        else labels["paid"].format(amount=format_kzt(order.total_kzt))
    )
    text_blocks.append(money)
    html_blocks.append(
        '<p style="padding:8px 12px;background:#fffbeb;border:1px solid #f59e0b;'
        f'border-radius:6px">{html.escape(money)}</p>'
    )

    base = get_settings().public_base_url.rstrip("/")
    msg = render(
        "order_confirmed",
        locale,
        to=user.email,
        action_url=f"{base}/{locale}/tickets",
        extra_text="\n".join(text_blocks),
        extra_html="".join(html_blocks),
        attachments=attachments,
        name=user.full_name,
        reference=order.reference,
        event=event.title,
        when=format_when(event),
        venue=_venue(event),
    )
    notification = await record_email(
        session,
        user_id=user.id,
        type=NotificationType.REGISTRATION_CONFIRMATION,
        msg=msg,
        event_id=event.id,
        order_id=order.id,
    )
    return [(msg, notification.id)]


async def payment_failed(session: AsyncSession, order: Order) -> Outbound:
    user = await session.get_one(User, order.user_id)
    event = await session.get_one(Event, order.event_id)
    locale = normalize_locale(user.locale)
    base = get_settings().public_base_url.rstrip("/")
    msg = render(
        "payment_failed",
        locale,
        to=user.email,
        action_url=f"{base}/{locale}/events/{event.slug}",
        name=user.full_name,
        reference=order.reference,
        event=event.title,
    )
    notification = await record_email(
        session,
        user_id=user.id,
        type=NotificationType.PAYMENT_FAILURE,
        msg=msg,
        event_id=event.id,
        order_id=order.id,
    )
    return [(msg, notification.id)]
