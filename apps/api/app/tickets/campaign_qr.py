"""Campaign QR images (SRS 4.14): "visually and functionally distinct from an admission-ticket
QR code".

* **Functionally:** it encodes the campaign link (`…/c/BFC1.<token>`), which check-in always
  rejects (`app.services.checkin`), and carries no price or discount.
* **Visually:** dark-purple modules inside a dashed purple frame, with a banner that reads
  "PROMO · NOT A TICKET" (translated) above the code. Ticket QRs are plain black on white.
"""

import io
from html import escape

import segno
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from app.i18n import Locale
from app.i18n.documents import CAMPAIGN_QR
from app.tickets.pdf import BOLD, REGULAR, draw_qr, draw_wrapped, register_fonts

FRAME = "#7c3aed"  # purple, clearly not a black-and-white ticket
MODULES = "#3b0764"  # very dark purple: high contrast for scanners, still visibly different


def _modules(payload: str) -> list[list[bool]]:
    return [
        [bool(m) for m in row]
        for row in segno.make(payload, error="m", micro=False).matrix_iter(border=4)
    ]


def campaign_qr_svg(
    url: str, event_title: str, campaign_name: str, code: str, locale: Locale
) -> str:
    labels = CAMPAIGN_QR[locale]
    rows = _modules(url)
    module = 8
    qr = len(rows) * module
    pad = 28
    width = qr + 2 * pad
    banner_h, footer_h = 56, 92
    height = banner_h + qr + footer_h + 2 * pad
    squares = "".join(
        f'<rect x="{pad + c * module}" y="{pad + banner_h + r * module}" '
        f'width="{module}" height="{module}"/>'
        for r, row in enumerate(rows)
        for c, dark in enumerate(row)
        if dark
    )
    font = "DejaVu Sans, Arial, Helvetica, sans-serif"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(labels["banner"])}: '
        f'{escape(event_title)}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>'
        f'<rect x="6" y="6" width="{width - 12}" height="{height - 12}" rx="18" fill="none" '
        f'stroke="{FRAME}" stroke-width="6" stroke-dasharray="18 10"/>'
        f'<rect x="{pad}" y="{pad}" width="{qr}" height="{banner_h - 10}" rx="8" fill="{FRAME}"/>'
        f'<text x="{width / 2}" y="{pad + 32}" text-anchor="middle" font-family="{font}" '
        f'font-size="22" font-weight="bold" fill="#ffffff">{escape(labels["banner"])}</text>'
        f'<g fill="{MODULES}">{squares}</g>'
        f'<text x="{width / 2}" y="{pad + banner_h + qr + 28}" text-anchor="middle" '
        f'font-family="{font}" font-size="18" font-weight="bold" fill="#111827">'
        f"{escape(event_title[:48])}</text>"
        f'<text x="{width / 2}" y="{pad + banner_h + qr + 54}" text-anchor="middle" '
        f'font-family="{font}" font-size="16" fill="#111827">{escape(labels["code"])}: '
        f'<tspan font-weight="bold">{escape(code)}</tspan> · {escape(campaign_name[:40])}</text>'
        f'<text x="{width / 2}" y="{pad + banner_h + qr + 78}" text-anchor="middle" '
        f'font-family="{font}" font-size="13" fill="#4b5563">{escape(labels["no_entry"])}</text>'
        "</svg>"
    )


def campaign_qr_pdf(
    url: str, event_title: str, campaign_name: str, code: str, locale: Locale
) -> bytes:
    """An A5 poster to print and put up."""
    register_fonts()
    labels = CAMPAIGN_QR[locale]
    buffer = io.BytesIO()
    page_w, page_h = A5
    canvas = Canvas(buffer, pagesize=A5, pageCompression=1)
    canvas.setTitle(f"{labels['banner']}: {event_title}")
    canvas.setAuthor("BiletFlow")

    canvas.setStrokeColor(FRAME)
    canvas.setLineWidth(3)
    canvas.setDash(9, 5)
    canvas.roundRect(6 * mm, 6 * mm, page_w - 12 * mm, page_h - 12 * mm, 6 * mm, stroke=1, fill=0)
    canvas.setDash()

    banner_y = page_h - 28 * mm
    canvas.setFillColor(FRAME)
    canvas.roundRect(14 * mm, banner_y, page_w - 28 * mm, 14 * mm, 3 * mm, stroke=0, fill=1)
    canvas.setFillColor("#ffffff")
    canvas.setFont(BOLD, 18)
    canvas.drawCentredString(page_w / 2, banner_y + 4.5 * mm, labels["banner"])

    size = 80 * mm
    qr_y = banner_y - 6 * mm - size
    draw_qr(canvas, url, (page_w - size) / 2, qr_y, size, color=MODULES)

    canvas.setFillColor("#111827")
    y = qr_y - 9 * mm
    y = draw_wrapped(canvas, event_title, 14 * mm, y, page_w - 28 * mm, BOLD, 15)
    canvas.setFont(REGULAR, 12)
    canvas.drawString(14 * mm, y - 1 * mm, f"{labels['code']}: {code} · {campaign_name}")
    y = draw_wrapped(canvas, labels["scan"], 14 * mm, y - 9 * mm, page_w - 28 * mm, REGULAR, 10)
    canvas.setFillColor("#4b5563")
    draw_wrapped(canvas, labels["no_entry"], 14 * mm, y - 1 * mm, page_w - 28 * mm, REGULAR, 10)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()
