"""Scanner app requirements that span several features (docs/scanner-requirements-check.md):
paper and digital copies of a ticket are one admission (SRS 4.7, UC7), a real Campaign QR is
never admission (SRS 4.14, 11), the two-second target on the demo seed (SRS 7), and every
door action reaching the event's activity timeline (SRS 4.16)."""

import io
import statistics
import time
from typing import Any

import httpx
import zxingcpp
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TicketStatus
from app.main import API_PREFIX
from app.models import Event, StaffAssignment, Ticket, User
from app.seed import JAZZ_SLUG, PASSWORD, seed
from app.services.mail import OutgoingEmail
from tests.factories import bearer
from tests.test_checkin import make_door, scan
from tests.test_documents import buy, decode_grayscale, setup


def _decode_png(png: bytes) -> list[str]:
    image = Image.open(io.BytesIO(png)).convert("L")
    return [r.text for r in zxingcpp.read_barcodes(image)]


async def test_email_qr_then_printed_pdf_qr_is_already_used(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    """SRS 4.7: "Digital and printed copies of the same ticket shall share one ticket
    identifier and shall not create separate admissions". Uses what the attendee actually
    receives: the QR image in the confirmation email and the attached PDF, both decoded with
    zxing; the PDF is rendered in grayscale, as from an office printer."""
    event, tt, buyer, owner = await setup(session)
    order = await buy(client, event, tt, buyer, ["Aigerim Bekova"])
    (ticket,) = order["tickets"]
    (message,) = [m for m in mail if m.template == "order_confirmed"]

    (qr_image,) = [a for a in message.attachments if a.mime_type == "image/png"]
    assert qr_image.inline_cid and f"cid:{qr_image.inline_cid}" in message.html
    (email_payload,) = _decode_png(qr_image.content)
    assert email_payload == ticket["qr_payload"]
    (pdf,) = [a.content for a in message.attachments if a.mime_type == "application/pdf"]
    printed = {dpi: decode_grayscale(pdf, dpi) for dpi in (72, 150, 300)}
    assert printed == {dpi: [email_payload] for dpi in printed}  # one identifier, one code

    scan_url = f"{API_PREFIX}/checkin/events/{event.id}/scan"
    first = await client.post(scan_url, headers=bearer(owner), json={"payload": email_payload})
    assert first.json()["result"] == "valid"
    for dpi, (paper_payload,) in printed.items():
        again = await client.post(scan_url, headers=bearer(owner), json={"payload": paper_payload})
        body = again.json()
        assert body["result"] == "already_used", dpi
        assert body["ticket"]["id"] == ticket["id"]
        assert body["ticket"]["checked_in_at"] == first.json()["ticket"]["checked_in_at"]
    assert body["stats"] == {"registered": 1, "checked_in": 1}


async def test_real_campaign_qr_is_rejected_and_the_next_ticket_still_works(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """SRS 4.14 / 11: "An admission scanner rejects Campaign QR Codes while continuing to
    accept valid ticket QR codes". The payload is decoded from the generated Campaign QR
    PDF, exactly as the phone's camera would read it."""
    door = await make_door(client, session)
    base = f"{API_PREFIX}/organizer/events/{door.event.id}/campaigns"
    created = await client.post(
        base,
        headers=bearer(door.owner),
        json={"name": "Poster", "discount_type": "percentage", "discount_percent": 25},
    )
    assert created.status_code == 201, created.text
    pdf = (
        await client.get(f"{base}/{created.json()['id']}/qr.pdf", headers=bearer(door.owner))
    ).content
    (campaign_payload,) = decode_grayscale(pdf, 150)
    assert campaign_payload == created.json()["campaign_url"]

    for user in (door.staff, door.admin, door.owner):
        rejected = await scan(client, door, campaign_payload, user=user)
        assert (rejected["result"], rejected["reason"], rejected["ticket"]) == (
            "invalid",
            "campaign_qr_not_admission",
            None,
        )
    # The manual check-in endpoint can't be talked into it either: it takes ticket ids only.
    manual = await client.post(
        door.url(f"/tickets/{campaign_payload}/check-in"), headers=bearer(door.staff)
    )
    assert manual.status_code in (404, 422)

    admitted = await scan(client, door, door.tickets[0]["qr_payload"])
    assert admitted["result"] == "valid"
    assert admitted["stats"] == {"registered": 3, "checked_in": 1}


async def test_checkin_under_2s_on_seeded_demo_data(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """SRS 7: "QR validation should normally complete within two seconds". Runs on the demo
    seed as the seeded Event Admin, signed in through the real login, and times every door
    request the app makes. In-process, so it measures the server, not the venue network."""
    await seed()
    staff = await session.scalar(select(User).where(User.email == "staff@demo.biletflow.kz"))
    jazz = await session.scalar(select(Event).where(Event.slug == JAZZ_SLUG))
    assert staff is not None and jazz is not None
    assert await session.scalar(
        select(StaffAssignment.id).where(
            StaffAssignment.user_id == staff.id, StaffAssignment.event_id == jazz.id
        )
    )
    login = await client.post(
        f"{API_PREFIX}/auth/login",
        headers={"X-Client": "scanner"},
        json={"email": staff.email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    tickets = (
        await session.scalars(
            select(Ticket).where(Ticket.event_id == jazz.id, Ticket.status == TicketStatus.VALID)
        )
    ).all()
    assert tickets, "the demo seed should have valid Jazz Night tickets"

    url = f"{API_PREFIX}/checkin/events/{jazz.id}"
    timings: list[float] = []

    async def timed(method: str, path: str, json: Any = None) -> dict[str, Any]:
        started = time.perf_counter()
        response = await client.request(method, url + path, headers=headers, json=json)
        timings.append(time.perf_counter() - started)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    for _ in range(3):  # scan, scan again, undo: every door action, several times over
        for ticket in tickets:
            assert (await timed("POST", "/scan", {"payload": ticket.admission_token}))[
                "result"
            ] == "valid"
            assert (await timed("POST", "/scan", {"payload": ticket.admission_token}))[
                "result"
            ] == "already_used"
            await timed("POST", f"/tickets/{ticket.id}/undo", {})
    await timed("GET", "/stats")
    await timed("GET", "/attendees?q=a")

    p95 = statistics.quantiles(timings, n=20)[-1]
    assert max(timings) < 2.0, f"slowest {max(timings):.3f}s, p95 {p95:.3f}s"


async def test_scan_manual_check_in_and_undo_all_reach_the_timeline(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """SRS 4.16: the timeline includes "check-ins, and check-in reversals", each with a
    timestamp, acting user, action type, affected entity and description. Rejected scans
    record nothing."""
    door = await make_door(client, session)
    scanned, searched = door.tickets[0], door.tickets[1]
    await scan(client, door, scanned["qr_payload"], user=door.staff)
    await scan(client, door, scanned["qr_payload"], user=door.staff)  # already used
    await scan(client, door, "https://biletflow.kz/c/BFC1.q8Zk2mWv0dX9yTnE4hRp")  # promo
    manual = await client.post(
        door.url(f"/tickets/{searched['id']}/check-in"), headers=bearer(door.admin)
    )
    assert manual.json()["result"] == "valid"
    undo = await client.post(
        door.url(f"/tickets/{scanned['id']}/undo"), headers=bearer(door.admin), json={}
    )
    assert undo.status_code == 200

    timeline = await client.get(
        f"{API_PREFIX}/history/events/{door.event.id}/timeline",
        headers=bearer(door.owner),
        params={"category": "ticket"},
    )
    assert timeline.status_code == 200, timeline.text
    entries = [e for e in timeline.json()["entries"] if "check" in e["action"]]
    assert [(e["action"], e["entity_id"]) for e in entries] == [  # newest first
        ("ticket.check_in_reversed", scanned["id"]),
        ("ticket.checked_in", searched["id"]),
        ("ticket.checked_in", scanned["id"]),
    ]
    reversal, by_search, by_scan = entries
    assert (reversal["actor_name"], by_search["actor_name"], by_scan["actor_name"]) == (
        door.admin.full_name,
        door.admin.full_name,
        door.staff.full_name,
    )
    assert "manual_search" in by_search["description"]
    assert "qr_scan" in by_scan["description"]
    assert scanned["ticket_number"] in by_scan["description"]
    assert all(e["occurred_at"] and e["entity_type"] == "ticket" for e in entries)

    # Check-in staff may scan, but the history is the organizer's (SRS 4.16).
    hidden = await client.get(
        f"{API_PREFIX}/history/events/{door.event.id}/timeline", headers=bearer(door.staff)
    )
    assert hidden.status_code == 404
