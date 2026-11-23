"""SRS UC1 and §11 "an organizer can publish a free event and distribute valid tickets",
end to end over the public API only (no factories, no SQL).

An organizer signs up and verifies their email, creates an event with only a free ticket
type, previews the draft and publishes it without any paid-sales activation (SRS 3.1: free
events cost nothing). An attendee then registers without payment details (SRS 4.4) and gets a
zero-total order, a valid signed QR ticket and a confirmation email, and the registration
shows in the organizer's attendee list.
"""

from typing import Any

import httpx

from app.main import API_PREFIX
from app.services.mail import OutgoingEmail
from app.tickets.tokens import parse_admission_token
from tests.e2e.test_report3_flow import _signup

A = API_PREFIX


async def test_uc1_free_event_is_published_and_hands_out_valid_tickets(
    client: httpx.AsyncClient, mail: list[OutgoingEmail]
) -> None:
    org = await _signup(client, mail, "free-organizer@e2e.kz", "organizer")

    # Organizer: event details and one free ticket type.
    event: dict[str, Any] = (
        await client.post(
            f"{A}/organizer/events",
            headers=org,
            json={
                "title": "UC1 Free Meetup",
                "venue": {"name": "Abay Hall", "address_line1": "Abay 1", "city": "Almaty"},
                "starts_at": "2027-04-10T18:00",
                "ends_at": "2027-04-10T20:00",
                "timezone": "Asia/Almaty",
            },
        )
    ).json()
    ev = event["id"]
    assert event["status"] == "draft"
    free = await client.post(
        f"{A}/organizer/events/{ev}/ticket-types",
        headers=org,
        json={"name": "Free entry", "price_kzt": 0, "quantity_total": 30},
    )
    assert free.status_code == 201, free.text
    free_id = free.json()["id"]

    # Preview before publication: the organizer sees it, the public doesn't yet.
    preview = (await client.get(f"{A}/organizer/events/{ev}/preview", headers=org)).json()
    assert preview["preview"] is True and preview["status"] == "draft"
    assert [t["name"] for t in preview["ticket_types"]] == ["Free entry"]
    assert (await client.get(f"{A}/events/{event['slug']}")).status_code == 404

    # Publish with no activation at all.
    published = await client.post(f"{A}/organizer/events/{ev}/publish", headers=org)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    # Attendee: the event is public and open, and registering needs no payment.
    att = await _signup(client, mail, "free-attendee@e2e.kz", "attendee")
    page = (await client.get(f"{A}/events/{event['slug']}")).json()
    assert page["registration_open"] is True
    assert page["paid_sales_enabled"] is False
    order = await client.post(
        f"{A}/orders",
        headers=att,
        json={"event_id": ev, "items": [{"ticket_type_id": free_id, "quantity": 1}]},
    )
    assert order.status_code == 201, order.text
    body = order.json()
    assert body["status"] == "confirmed"
    assert body["total_kzt"] == 0
    assert body["payment_required"] is False
    [ticket] = body["tickets"]
    assert ticket["status"] == "valid"
    assert str(parse_admission_token(ticket["qr_payload"])) == ticket["id"]

    # The confirmation email carries the QR ticket.
    [confirmation] = [
        m for m in mail if m.to == "free-attendee@e2e.kz" and m.template == "order_confirmed"
    ]
    assert ticket["ticket_number"] in confirmation.text
    assert any(a.inline_cid is not None for a in confirmation.attachments)

    # The organizer sees the registration in the attendee list.
    attendees = (await client.get(f"{A}/organizer/events/{ev}/attendees", headers=org)).json()
    assert [a["ticket_number"] for a in attendees["attendees"]] == [ticket["ticket_number"]]
