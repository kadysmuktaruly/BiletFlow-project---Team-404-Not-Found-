"""SRS 4.7 / UC7 print-optimized PDF tickets and SRS 4.14 Campaign QR images.

The PDFs are rendered to grayscale bitmaps with pdfium and decoded with zxing, so these tests
check what a scanner would actually read, not just what we meant to draw.
"""

import uuid
from typing import Any

import httpx
import pypdfium2 as pdfium
import zxingcpp
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.i18n.documents import CAMPAIGN_QR, TICKET_PDF, TICKET_STATUS
from app.main import API_PREFIX
from app.models import Event, OrganizerProfile, Ticket, TicketType, User, Venue
from app.services.mail import OutgoingEmail
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)


def pdf_text(pdf: bytes) -> str:
    page = pdfium.PdfDocument(pdf)[0]
    text: str = page.get_textpage().get_text_range()
    return text


def decode_grayscale(pdf: bytes, dpi: int) -> list[str]:
    """Render page 1 in grayscale at `dpi` and read every QR code on it."""
    image = pdfium.PdfDocument(pdf)[0].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
    return [r.text for r in zxingcpp.read_barcodes(image)]


async def setup(
    session: AsyncSession, locale: str = "en", price_kzt: int = 0
) -> tuple[Event, TicketType, User, User]:
    organizer = await make_organizer(session)
    venue = Venue(
        name="Kazakhconcert Hall",
        address_line1="Abay Ave 1",
        city="Almaty",
    )
    session.add(venue)
    await session.flush()
    event = await make_published_event(
        session, organizer, title="Almaty Jazz Night", venue_id=venue.id
    )
    ticket_type = await make_ticket_type(session, event, name="Balcony", price_kzt=price_kzt)
    await enable_paid_sales(session, event)
    buyer = await make_user(session, locale=locale)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    await session.commit()
    return event, ticket_type, buyer, owner


async def buy(
    client: httpx.AsyncClient, event: Event, tt: TicketType, buyer: User, names: list[str]
) -> dict[str, Any]:
    response = await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={
            "event_id": str(event.id),
            "items": [{"ticket_type_id": str(tt.id), "quantity": len(names)}],
            "attendees": [{"full_name": n} for n in names],
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def pay(client: httpx.AsyncClient, order: dict[str, Any], buyer: User) -> dict[str, Any]:
    response = await client.post(
        f"{API_PREFIX}/orders/{order['id']}/payments",
        headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "succeed"},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = (
        await client.get(f"{API_PREFIX}/orders/{order['id']}", headers=bearer(buyer))
    ).json()
    return body


# --- the PDF ticket -----------------------------------------------------------------------


async def test_pdf_ticket_has_every_field_and_no_payment_data(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer, _ = await setup(session, price_kzt=18_500)
    order = await pay(client, await buy(client, event, tt, buyer, ["Aigerim Bekova"]), buyer)
    ticket = order["tickets"][0]

    response = await client.get(
        f"{API_PREFIX}/me/tickets/{ticket['id']}/pdf", headers=bearer(buyer)
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert (
        f'filename="ticket-{ticket["ticket_number"]}.pdf"'
        in response.headers["content-disposition"]
    )
    pdf = response.content
    assert pdf.startswith(b"%PDF")
    assert len(pdfium.PdfDocument(pdf)) == 1
    width, height = pdfium.PdfDocument(pdf)[0].get_size()
    assert (round(width), round(height)) == (595, 842)  # A4 in points

    text = pdf_text(pdf)
    for expected in (
        "Almaty Jazz Night",
        "Kazakhconcert Hall",
        "Abay Ave 1",
        "Asia/Almaty",
        "Balcony",
        "Aigerim Bekova",
        ticket["ticket_number"],
        "Valid",
    ):
        assert expected in text, expected
    # SRS 4.7: no payment-card details or other unnecessary sensitive information.
    for forbidden in (
        "18500",
        "18 500",
        "18,500",
        "KZT",
        "₸",
        "DEMO",
        order["reference"],
        "card",
        "Card",
    ):
        assert forbidden not in text, forbidden


async def test_pdf_qr_scans_from_a_grayscale_print_and_matches_the_digital_ticket(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """SRS 4.7: scannable "including when printed in grayscale"; digital and printed copies
    "share one ticket identifier". 72 dpi is far below any office printer."""
    event, tt, buyer, _ = await setup(session)
    order = await buy(client, event, tt, buyer, ["One", "Two"])
    for ticket in order["tickets"]:
        pdf = (
            await client.get(f"{API_PREFIX}/me/tickets/{ticket['id']}/pdf", headers=bearer(buyer))
        ).content
        for dpi in (72, 150, 300):
            assert decode_grayscale(pdf, dpi) == [ticket["qr_payload"]], dpi
        assert ticket["ticket_number"] in pdf_text(pdf)

    # The printed QR is the admission token: scanning it checks the same ticket in once.
    owner_id = await session.scalar(select_owner(event))
    owner = await session.get(User, owner_id)
    assert owner is not None
    pdf = (
        await client.get(
            f"{API_PREFIX}/me/tickets/{order['tickets'][0]['id']}/pdf", headers=bearer(buyer)
        )
    ).content
    (payload,) = decode_grayscale(pdf, 150)
    scan_url = f"{API_PREFIX}/checkin/events/{event.id}/scan"
    first = await client.post(scan_url, headers=bearer(owner), json={"payload": payload})
    digital = await client.post(
        scan_url, headers=bearer(owner), json={"payload": order["tickets"][0]["qr_payload"]}
    )
    assert (first.json()["result"], digital.json()["result"]) == ("valid", "already_used")


def select_owner(event: Event) -> Any:
    return select(OrganizerProfile.user_id).where(OrganizerProfile.id == event.organizer_profile_id)


async def test_pdf_in_kazakh_and_russian(client: httpx.AsyncClient, session: AsyncSession) -> None:
    for locale, title in (("kk", "Кіру билеті"), ("ru", "Входной билет")):
        event, tt, buyer, _ = await setup(session, locale=locale)
        order = await buy(client, event, tt, buyer, ["Әлия Қасымова"])
        pdf = (
            await client.get(
                f"{API_PREFIX}/me/tickets/{order['tickets'][0]['id']}/pdf", headers=bearer(buyer)
            )
        ).content
        text = pdf_text(pdf)
        assert title in text
        assert "Әлия Қасымова" in text  # Kazakh letters render as text, not boxes
        assert TICKET_STATUS[locale]["valid"] in text  # type: ignore[index]


async def test_pdf_shows_seat_and_live_status(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer, _ = await setup(session)
    order = await buy(client, event, tt, buyer, ["Seated Guest"])
    ticket_id = uuid.UUID(order["tickets"][0]["id"])
    await session.execute(
        update(Ticket)
        .where(Ticket.id == ticket_id)
        .values(seat_section="B", seat_row="7", seat_number="12", status="refunded")
    )
    await session.commit()
    text = pdf_text(
        (
            await client.get(f"{API_PREFIX}/me/tickets/{ticket_id}/pdf", headers=bearer(buyer))
        ).content
    )
    assert "Section B, row 7, seat 12" in text
    assert "Refunded" in text
    assert "not valid for entry" in text


async def test_only_the_buyer_can_download_the_pdf(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, buyer, owner = await setup(session)
    order = await buy(client, event, tt, buyer, ["Mine"])
    stranger = await make_user(session)
    await session.commit()
    url = f"{API_PREFIX}/me/tickets/{order['tickets'][0]['id']}/pdf"
    for user in (stranger, owner):
        assert (await client.get(url, headers=bearer(user))).status_code == 404
    assert (await client.get(url)).status_code == 401


async def test_confirmation_email_attaches_a_pdf_per_ticket(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, buyer, _ = await setup(session)
    order = await buy(client, event, tt, buyer, ["First Guest", "Second Guest"])
    (message,) = [m for m in mail if m.template == "order_confirmed"]
    pdfs = [a for a in message.attachments if a.mime_type == "application/pdf"]
    assert sorted(a.filename for a in pdfs) == sorted(
        f"ticket-{t['ticket_number']}.pdf" for t in order["tickets"]
    )
    for attachment, ticket in zip(
        sorted(pdfs, key=lambda a: a.filename),
        sorted(order["tickets"], key=lambda t: f"ticket-{t['ticket_number']}.pdf"),
        strict=True,
    ):
        assert attachment.inline_cid is None  # a real attachment, not an inline image
        assert decode_grayscale(attachment.content, 100) == [ticket["qr_payload"]]


def test_document_strings_have_the_same_keys_in_every_locale() -> None:
    for table in (TICKET_PDF, TICKET_STATUS, CAMPAIGN_QR):
        keys = {locale: set(strings) for locale, strings in table.items()}
        assert set(keys) == {"kk", "ru", "en"}
        assert keys["kk"] == keys["ru"] == keys["en"]


# --- the Campaign QR ----------------------------------------------------------------------


async def test_campaign_qr_is_labelled_promo_and_encodes_only_the_link(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, _, _, owner = await setup(session)
    base = f"{API_PREFIX}/organizer/events/{event.id}/campaigns"
    created = (
        await client.post(
            base,
            headers=bearer(owner),
            json={
                "name": "Poster",
                "discount_type": "percentage",
                "discount_percent": 25,
                "code": "POSTER25",
            },
        )
    ).json()

    pdf_response = await client.get(
        f"{base}/{created['id']}/qr.pdf", headers=bearer(owner), params={"lang": "en"}
    )
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    pdf = pdf_response.content
    assert decode_grayscale(pdf, 100) == [created["campaign_url"]]
    text = pdf_text(pdf)
    assert "PROMO · NOT A TICKET" in text
    assert "POSTER25" in text

    svg = await client.get(
        f"{base}/{created['id']}/qr.svg", headers=bearer(owner), params={"lang": "ru"}
    )
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert "ПРОМО · НЕ БИЛЕТ" in svg.text
    assert "stroke-dasharray" in svg.text
    assert "25" not in created["campaign_url"]  # the link carries no discount

    # At the door, the Campaign QR is never admission (SRS 4.14).
    scan = await client.post(
        f"{API_PREFIX}/checkin/events/{event.id}/scan",
        headers=bearer(owner),
        json={"payload": created["campaign_url"]},
    )
    assert (scan.json()["result"], scan.json()["reason"]) == (
        "invalid",
        "campaign_qr_not_admission",
    )

    stranger_event, _, _, stranger = await setup(session)
    assert (
        await client.get(f"{base}/{created['id']}/qr.pdf", headers=bearer(stranger))
    ).status_code == 404
    assert (
        await client.get(f"{base}/{created['id']}/qr.png", headers=bearer(owner))
    ).status_code == 422
