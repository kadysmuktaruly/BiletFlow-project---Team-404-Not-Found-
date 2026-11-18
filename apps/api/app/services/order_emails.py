"""Order emails (SRS 4.4, 4.6, 4.10): the confirmation with every QR ticket, and the DEMO
payment-failure notice."""

import html
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NotificationType
from app.i18n import normalize_locale
from app.i18n.emails import TICKET_LABELS
from app.models import Event, Order, Ticket, User
from app.services.mail import Attachment, Outbound
from app.services.notifications import Message, notify
from app.tickets.pdf import render_ticket_pdf
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
    from app.services.orders import ticket_documents, tickets_read  # avoid an import cycle

    user = await session.get_one(User, order.user_id)
    event = await session.get_one(Event, order.event_id)
    locale = normalize_locale(user.locale)
    labels = TICKET_LABELS[locale]
    tickets = list(
        await session.scalars(select(Ticket).where(Ticket.order_id == order.id).order_by(Ticket.id))
    )
    reads = await tickets_read(session, tickets)
    documents = await ticket_documents(session, tickets)
    printed_at = datetime.now(UTC)

    attachments: list[Attachment] = []
    text_blocks: list[str] = []
    html_blocks: list[str] = []
    for read, document in zip(reads, documents, strict=True):
        cid = f"qr-{read.id}@biletflow"
        attachments.append(
            Attachment(
                f"ticket-{read.ticket_number}.png", qr_png(read.qr_payload), "image/png", cid
            )
        )
        # SRS 4.7 / UC7: the print-optimized PDF of the same ticket, attached.
        attachments.append(
            Attachment(
                f"ticket-{read.ticket_number}.pdf",
                render_ticket_pdf(document, locale, printed_at),
                "application/pdf",
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

    return await notify(
        session,
        user,
        Message(
            type=NotificationType.REGISTRATION_CONFIRMATION,
            template="order_confirmed",
            params={
                "reference": order.reference,
                "event": event.title,
                "when": format_when(event),
                "venue": _venue(event),
            },
            action_path="/tickets",
            event_id=event.id,
            order_id=order.id,
            attachments=attachments,
            extra_text="\n".join(text_blocks),
            extra_html="".join(html_blocks),
        ),
    )


async def payment_failed(session: AsyncSession, order: Order) -> Outbound:
    user = await session.get_one(User, order.user_id)
    event = await session.get_one(Event, order.event_id)
    return await notify(
        session,
        user,
        Message(
            type=NotificationType.PAYMENT_FAILURE,
            template="payment_failed",
            params={"reference": order.reference, "event": event.title},
            action_path=f"/events/{event.slug}",
            event_id=event.id,
            order_id=order.id,
        ),
    )
