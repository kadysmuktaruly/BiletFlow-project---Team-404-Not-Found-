"""Report 3 checkpoint, end to end over the public API only (no factories, no SQL).

An organizer signs up, verifies their email, creates an event with a free and a paid ticket
type, completes the DEMO paid-sales checklist and publishes. An attendee signs up, registers
for free, buys a paid ticket through the DEMO payment, and receives both confirmation emails
with QR tickets. This is the same flow as docs/demo-report-3.md, minus the browser.
"""

import re
import uuid
from typing import Any

import httpx

from app.main import API_PREFIX
from app.services.mail import OutgoingEmail
from app.tickets.tokens import parse_admission_token

A = API_PREFIX


def _token(mail: list[OutgoingEmail], to: str, template: str) -> str:
    msg = next(m for m in reversed(mail) if m.to == to and m.template == template)
    match = re.search(r"token=([\w.\-]+)", msg.text)
    assert match, msg.text
    return match.group(1)


async def _signup(
    client: httpx.AsyncClient, mail: list[OutgoingEmail], email: str, role: str
) -> dict[str, str]:
    password = "s3cret-pass-123"
    r = await client.post(
        f"{A}/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": email.split("@")[0],
            "role": role,
            "locale": "en",
        },
    )
    assert r.status_code == 202
    r = await client.post(
        f"{A}/auth/verify-email", json={"token": _token(mail, email, "verify_email")}
    )
    assert r.json()["is_email_verified"] is True
    r = await client.post(f"{A}/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_report3_free_registration_and_demo_paid_purchase(
    client: httpx.AsyncClient, mail: list[OutgoingEmail]
) -> None:
    org = await _signup(client, mail, "organizer@e2e.kz", "organizer")

    # Organizer: event, ticket types, payout account, checklist, publish.
    event: dict[str, Any] = (
        await client.post(
            f"{A}/organizer/events",
            headers=org,
            json={
                "title": "Report 3 Demo Night",
                "venue": {
                    "name": "Esentai Hall",
                    "address_line1": "Al-Farabi 77",
                    "city": "Almaty",
                },
                "starts_at": "2027-03-20T19:00",
                "ends_at": "2027-03-20T22:00",
                "timezone": "Asia/Almaty",
            },
        )
    ).json()
    ev = event["id"]
    free = (
        await client.post(
            f"{A}/organizer/events/{ev}/ticket-types",
            headers=org,
            json={"name": "Free entry", "price_kzt": 0, "quantity_total": 50},
        )
    ).json()
    paid = (
        await client.post(
            f"{A}/organizer/events/{ev}/ticket-types",
            headers=org,
            json={"name": "Standard", "price_kzt": 8000, "quantity_total": 20},
        )
    ).json()
    await client.put(
        f"{A}/organizer/payout-account",
        headers=org,
        json={"account_holder_name": "Org", "bank_name": "Demo Bank", "account_last4": "4321"},
    )
    for step in ("identity", "payout-account", "terms"):
        assert (
            await client.post(
                f"{A}/organizer/events/{ev}/activation/{step}", headers=org, json={"confirm": True}
            )
        ).status_code == 200
    activation = (
        await client.post(
            f"{A}/organizer/events/{ev}/activation/fee-payment",
            headers={**org, "Idempotency-Key": str(uuid.uuid4())},
            json={"outcome": "succeed"},
        )
    ).json()
    assert activation["status"] == "active"
    published = await client.post(f"{A}/organizer/events/{ev}/publish", headers=org)
    assert published.json()["status"] == "published"

    # Attendee: finds the event, registers for free, then buys a paid ticket.
    att = await _signup(client, mail, "attendee@e2e.kz", "attendee")
    listing = (await client.get(f"{A}/events")).json()
    assert event["slug"] in [e["slug"] for e in listing["items"]]
    page = (await client.get(f"{A}/events/{event['slug']}")).json()
    assert page["registration_open"] and page["paid_sales_enabled"]

    free_order = (
        await client.post(
            f"{A}/orders",
            headers=att,
            json={"event_id": ev, "items": [{"ticket_type_id": free["id"], "quantity": 1}]},
        )
    ).json()
    assert free_order["status"] == "confirmed" and free_order["total_kzt"] == 0

    paid_order = (
        await client.post(
            f"{A}/orders",
            headers=att,
            json={"event_id": ev, "items": [{"ticket_type_id": paid["id"], "quantity": 2}]},
        )
    ).json()
    assert paid_order["status"] == "awaiting_payment" and paid_order["total_kzt"] == 16000
    payment = (
        await client.post(
            f"{A}/orders/{paid_order['id']}/payments",
            headers={**att, "Idempotency-Key": str(uuid.uuid4())},
            json={"outcome": "succeed"},
        )
    ).json()
    assert payment["payment"]["demo"] is True
    assert payment["order"]["status"] == "confirmed"

    # Three QR tickets in "My tickets", each with a valid signed admission token.
    tickets = (await client.get(f"{A}/me/tickets", headers=att)).json()
    assert len(tickets) == 3
    assert all(parse_admission_token(t["qr_payload"]) is not None for t in tickets)

    # Two confirmation emails, each carrying one inline QR image per ticket.
    confirmations = [
        m for m in mail if m.to == "attendee@e2e.kz" and m.template == "order_confirmed"
    ]
    assert len(confirmations) == 2
    assert sorted(sum(a.inline_cid is not None for a in m.attachments) for m in confirmations) == [
        1,
        2,
    ]
    assert any("DEMO payment" in m.text for m in confirmations)
    for ticket in tickets:
        assert any(ticket["ticket_number"] in m.text for m in confirmations)
