"""Print-optimized PDF tickets (SRS 4.7, UC7, SRS 7).

One A4 page per ticket, built from the canonical ticket record:

* Every field SRS 4.7 lists: event name, date and time (in the event's own time zone), venue,
  ticket type, attendee, seat when assigned, ticket number and the QR code. Plus the status
  at the moment of printing.
* **No price, payment or card data.** Nothing from the order's money columns is passed in.
* **The same QR as the digital ticket.** It encodes `Ticket.admission_token`, so the printed
  and on-screen copies are one ticket and one admission.
* **Scannable from a grayscale print.** The QR is 70 mm wide, error correction M, pure black
  on white with a 4-module quiet zone, drawn as vector squares (no resampling blur).

Text uses the bundled DejaVu Sans, which covers Kazakh and Russian Cyrillic.
"""

import io
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

import segno
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from app.i18n import Locale
from app.i18n.documents import TICKET_PDF, TICKET_STATUS

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGULAR = "DejaVuSans"
BOLD = "DejaVuSans-Bold"
QR_SIZE = 70 * mm


@cache
def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))


@dataclass(frozen=True)
class TicketDocument:
    """What a printed ticket shows. Deliberately has no money fields."""

    ticket_number: str
    status: str  # TicketStatus value
    qr_payload: str
    ticket_type_name: str
    attendee_name: str
    event_title: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    venue_name: str | None
    venue_address: str | None
    seat_section: str | None = None
    seat_row: str | None = None
    seat_number: str | None = None


def draw_qr(
    canvas: Canvas, payload: str, x: float, y: float, size: float, color: str = "#000000"
) -> None:
    """Draw `payload` as a QR code with its bottom-left corner at (x, y), `size` wide,
    including the 4-module quiet zone, as filled vector squares."""
    rows = [list(row) for row in segno.make(payload, error="m", micro=False).matrix_iter(border=4)]
    module = size / len(rows)
    canvas.saveState()
    canvas.setFillColor("#ffffff")
    canvas.rect(x, y, size, size, stroke=0, fill=1)
    canvas.setFillColor(color)
    for r, row in enumerate(rows):
        top = y + size - (r + 1) * module
        c = 0
        while c < len(row):
            if row[c]:
                start = c
                while c < len(row) and row[c]:
                    c += 1
                # Overlap a hair so adjacent squares never show a hairline gap when printed.
                canvas.rect(
                    x + start * module, top, (c - start) * module + 0.05, module + 0.05, 0, 1
                )
            else:
                c += 1
    canvas.restoreState()


def draw_wrapped(
    canvas: Canvas, text: str, x: float, y: float, width: float, font: str, size: float
) -> float:
    """Draw wrapped text starting at baseline y; return the next free baseline."""
    canvas.setFont(font, size)
    for line in simpleSplit(text, font, size, width):
        canvas.drawString(x, y, line)
        y -= size * 1.3
    return y


def _when(doc: TicketDocument) -> str:
    zone = ZoneInfo(doc.timezone)
    start, end = doc.starts_at.astimezone(zone), doc.ends_at.astimezone(zone)
    until = f"{end:%H:%M}" if start.date() == end.date() else f"{end:%d.%m.%Y %H:%M}"
    return f"{start:%d.%m.%Y %H:%M} – {until} ({doc.timezone})"


def _fields(doc: TicketDocument, labels: dict[str, str], status: str) -> Iterable[tuple[str, str]]:
    yield labels["ticket_type"], doc.ticket_type_name
    yield labels["attendee"], doc.attendee_name
    if doc.seat_number:
        yield (
            labels["seat"],
            labels["seat_value"].format(
                section=doc.seat_section or "—", row=doc.seat_row or "—", number=doc.seat_number
            ),
        )
    yield labels["ticket_number"], doc.ticket_number
    yield labels["status"], status


def render_ticket_pdf(doc: TicketDocument, locale: Locale, printed_at: datetime) -> bytes:
    register_fonts()
    labels = TICKET_PDF[locale]
    status = TICKET_STATUS[locale].get(doc.status, doc.status)
    buffer = io.BytesIO()
    page_w, page_h = A4
    margin = 20 * mm
    width = page_w - 2 * margin
    canvas = Canvas(buffer, pagesize=A4, pageCompression=1)
    canvas.setTitle(f"{labels['doc_title']} {doc.ticket_number}")
    canvas.setAuthor("BiletFlow")
    canvas.setSubject(doc.event_title)

    # Header band. Thin, so it costs little toner in grayscale.
    y = page_h - margin
    canvas.setFont(BOLD, 14)
    canvas.drawString(margin, y, "BiletFlow")
    canvas.setFont(REGULAR, 11)
    canvas.drawRightString(page_w - margin, y, labels["doc_title"])
    canvas.setLineWidth(0.8)
    canvas.line(margin, y - 4 * mm, page_w - margin, y - 4 * mm)

    y -= 16 * mm
    y = draw_wrapped(canvas, doc.event_title, margin, y, width, BOLD, 22)
    y -= 2 * mm
    for label, value in (
        (labels["when"], _when(doc)),
        (labels["venue"], ", ".join(p for p in (doc.venue_name, doc.venue_address) if p) or "—"),
    ):
        canvas.setFont(REGULAR, 9)
        canvas.drawString(margin, y, label.upper())
        y = draw_wrapped(canvas, value, margin, y - 5 * mm, width, REGULAR, 13) - 2 * mm

    # The QR, centered, with the ticket number large beneath it.
    y -= 4 * mm
    qr_top = y
    draw_qr(canvas, doc.qr_payload, (page_w - QR_SIZE) / 2, qr_top - QR_SIZE, QR_SIZE)
    y = qr_top - QR_SIZE - 9 * mm
    canvas.setFont(BOLD, 20)
    canvas.drawCentredString(page_w / 2, y, doc.ticket_number)
    if doc.status in ("cancelled", "refunded"):
        y -= 9 * mm
        canvas.setFont(BOLD, 13)
        canvas.drawCentredString(page_w / 2, y, f"{status.upper()} · {labels['not_valid']}")

    # Field list.
    y -= 14 * mm
    for label, value in _fields(doc, labels, status):
        canvas.setFont(REGULAR, 9)
        canvas.drawString(margin, y, label.upper())
        y = draw_wrapped(canvas, value, margin + 45 * mm, y, width - 45 * mm, BOLD, 12) - 3 * mm

    # Footer.
    canvas.setLineWidth(0.5)
    canvas.line(margin, margin + 16 * mm, page_w - margin, margin + 16 * mm)
    draw_wrapped(canvas, labels["instructions"], margin, margin + 11 * mm, width, REGULAR, 9)
    canvas.setFont(REGULAR, 8)
    canvas.drawRightString(
        page_w - margin,
        margin - 2 * mm,
        f"{labels['printed_at']}: {printed_at.astimezone(ZoneInfo(doc.timezone)):%d.%m.%Y %H:%M}",
    )
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()
