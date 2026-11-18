"""SRS 4.8 check-in: signed token plus live status, five results, one admission per ticket
even when two devices scan at once, staff-only access, authorized undo, counts, manual
search, Campaign QR rejection (SRS 4.14) and the two-second target (SRS 7)."""

import asyncio
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CheckInMethod, StaffRole, TicketStatus, UserRole
from app.main import API_PREFIX
from app.models import (
    AuditLogEntry,
    CheckInRecord,
    Event,
    StaffAssignment,
    Ticket,
    User,
)
from app.tickets.tokens import sign_admission_token
from tests.factories import (
    bearer,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)


@dataclass
class Door:
    event: Event
    owner: User
    admin: User
    staff: User
    tickets: list[dict[str, Any]]  # TicketRead JSON from the order: id, qr_payload, ...

    def url(self, path: str = "") -> str:
        return f"{API_PREFIX}/checkin/events/{self.event.id}{path}"


def _assign(event: Event, user: User, role: StaffRole, by: uuid.UUID) -> StaffAssignment:
    return StaffAssignment(event_id=event.id, user_id=user.id, role=role, assigned_by_user_id=by)


async def make_door(
    client: httpx.AsyncClient,
    session: AsyncSession,
    names: tuple[str, ...] = ("Aigerim Bekova", "Daniyar Sadykov", "Ruslan 100%_Off"),
) -> Door:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer)
    ticket_type = await make_ticket_type(
        session, event, name="General", quantity_total=500, max_per_order=50
    )
    admin, staff, buyer = (
        await make_user(session),
        await make_user(session),
        await make_user(session),
    )
    session.add(_assign(event, admin, StaffRole.EVENT_ADMIN, organizer.user_id))
    session.add(_assign(event, staff, StaffRole.CHECK_IN_STAFF, organizer.user_id))
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    await session.commit()

    response = await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={
            "event_id": str(event.id),
            "items": [{"ticket_type_id": str(ticket_type.id), "quantity": len(names)}],
            "attendees": [
                {"full_name": n, "email": f"guest{i}@example.kz"} for i, n in enumerate(names)
            ],
        },
    )
    assert response.status_code == 201, response.text
    tickets = sorted(response.json()["tickets"], key=lambda t: names.index(t["attendee_name"]))
    return Door(event=event, owner=owner, admin=admin, staff=staff, tickets=tickets)


async def scan(
    client: httpx.AsyncClient, door: Door, payload: str, user: User | None = None
) -> dict[str, Any]:
    response = await client.post(
        door.url("/scan"), headers=bearer(user or door.staff), json={"payload": payload}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def set_status(session: AsyncSession, ticket_id: str, status: TicketStatus) -> None:
    await session.execute(
        update(Ticket).where(Ticket.id == uuid.UUID(ticket_id)).values(status=status)
    )
    await session.commit()


# --- the five results ---------------------------------------------------------------------


async def test_valid_scan_checks_in_once_then_already_used(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    first = await scan(client, door, door.tickets[0]["qr_payload"])
    assert first["result"] == "valid"
    assert first["method"] == "qr_scan"
    assert first["ticket"]["attendee_name"] == "Aigerim Bekova"
    assert first["ticket"]["status"] == "checked_in"
    assert first["stats"] == {"registered": 3, "checked_in": 1}

    again = await scan(client, door, door.tickets[0]["qr_payload"], user=door.admin)
    assert again["result"] == "already_used"
    assert again["ticket"]["checked_in_at"] == first["ticket"]["checked_in_at"]
    assert again["stats"] == {"registered": 3, "checked_in": 1}


async def test_cancelled_and_refunded_tickets_are_rejected_live(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """The QR token never changes; the status read at the door does (SRS 4.9: refunded or
    cancelled tickets become invalid)."""
    door = await make_door(client, session)
    await set_status(session, door.tickets[0]["id"], TicketStatus.CANCELLED)
    await set_status(session, door.tickets[1]["id"], TicketStatus.REFUNDED)

    cancelled = await scan(client, door, door.tickets[0]["qr_payload"])
    refunded = await scan(client, door, door.tickets[1]["qr_payload"])
    assert (cancelled["result"], cancelled["ticket"]["status"]) == ("cancelled", "cancelled")
    assert (refunded["result"], refunded["ticket"]["status"]) == ("refunded", "refunded")
    # Neither counts as registered any more.
    assert refunded["stats"] == {"registered": 1, "checked_in": 0}
    assert await session.scalar(select(func.count()).select_from(CheckInRecord)) == 0


async def test_forged_tampered_and_garbage_payloads_are_invalid(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    real = door.tickets[0]["qr_payload"]
    tampered = real[:-2] + ("AA" if not real.endswith("AA") else "BB")
    forged = "BFT1." + real.split(".")[1] + ".bm90LXRoZS1yZWFsLW1hYw"
    for payload in (tampered, forged, "hello", "https://example.com/ticket/123", " "):
        body = await scan(client, door, payload)
        assert (body["result"], body["reason"], body["ticket"]) == ("invalid", "unrecognized", None)
    assert await session.scalar(select(func.count()).select_from(CheckInRecord)) == 0


async def test_campaign_qr_is_never_admission(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """SRS 4.14: the scanner and admission endpoint never accept a Campaign QR."""
    door = await make_door(client, session)
    for payload in (
        "BFC1.q8Zk2mWv0dX9yTnE4hRp",
        "https://biletflow.kz/c/BFC1.q8Zk2mWv0dX9yTnE4hRp",
        "http://localhost:3000/en/c/BFC1.q8Zk2mWv0dX9yTnE4hRp",
    ):
        body = await scan(client, door, payload)
        assert (body["result"], body["reason"]) == ("invalid", "campaign_qr_not_admission")
    # Valid tickets keep working right after (SRS 11).
    assert (await scan(client, door, door.tickets[0]["qr_payload"]))["result"] == "valid"


async def test_another_events_ticket_is_invalid_and_not_described(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    other = await make_door(client, session)
    body = await scan(client, door, other.tickets[0]["qr_payload"])
    assert (body["result"], body["reason"], body["ticket"]) == ("invalid", "wrong_event", None)
    still = await scan(client, other, other.tickets[0]["qr_payload"])
    assert still["result"] == "valid"


async def test_signed_token_for_a_ticket_that_does_not_exist_is_invalid(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    body = await scan(client, door, sign_admission_token(uuid.uuid4()))
    assert (body["result"], body["reason"]) == ("invalid", "unrecognized")


# --- atomicity ----------------------------------------------------------------------------


async def test_double_scan_concurrent_one_checkin(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """Two (here: ten) devices scan the same ticket at the same moment. Exactly one gets
    `valid`; every other gets `already_used`; there is one check-in record."""
    door = await make_door(client, session)
    payload = door.tickets[0]["qr_payload"]
    devices = [door.staff, door.admin, door.owner] * 3 + [door.staff]

    results = await asyncio.gather(
        *(
            client.post(
                door.url("/scan"),
                headers=bearer(u),
                json={"payload": payload, "device_label": f"phone-{i}"},
            )
            for i, u in enumerate(devices)
        )
    )
    outcomes = sorted(r.json()["result"] for r in results)
    assert outcomes == ["already_used"] * (len(devices) - 1) + ["valid"], outcomes
    records = (await session.scalars(select(CheckInRecord))).all()
    assert len(records) == 1
    audit = await session.scalar(
        select(func.count())
        .select_from(AuditLogEntry)
        .where(AuditLogEntry.action_type == "ticket.checked_in")
    )
    assert audit == 1


async def test_manual_and_scan_racing_admit_once(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    ticket = door.tickets[1]
    results = await asyncio.gather(
        client.post(
            door.url("/scan"), headers=bearer(door.staff), json={"payload": ticket["qr_payload"]}
        ),
        client.post(door.url(f"/tickets/{ticket['id']}/check-in"), headers=bearer(door.admin)),
    )
    assert sorted(r.json()["result"] for r in results) == ["already_used", "valid"]


# --- access -------------------------------------------------------------------------------


async def test_only_owner_and_assigned_staff_can_use_the_door(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    stranger = await make_user(session)
    platform_admin = await make_user(session, role=UserRole.PLATFORM_ADMIN)
    revoked = await make_user(session)
    session.add(
        StaffAssignment(
            event_id=door.event.id,
            user_id=revoked.id,
            role=StaffRole.EVENT_ADMIN,
            assigned_by_user_id=door.owner.id,
            revoked_at=datetime.now(UTC),
        )
    )
    await session.commit()
    payload = door.tickets[0]["qr_payload"]

    for outsider in (stranger, platform_admin, revoked):
        for method, path, body in (
            ("POST", "/scan", {"payload": payload}),
            ("POST", f"/tickets/{door.tickets[0]['id']}/check-in", None),
            ("POST", f"/tickets/{door.tickets[0]['id']}/undo", None),
            ("GET", "/stats", None),
            ("GET", "/attendees?q=a", None),
        ):
            response = await client.request(
                method, door.url(path), headers=bearer(outsider), json=body
            )
            assert response.status_code == 404, (path, response.text)
            assert response.json()["error"]["code"] == "event_not_found"
    missing = await client.get(
        f"{API_PREFIX}/checkin/events/{uuid.uuid4()}/stats", headers=bearer(door.admin)
    )
    assert missing.status_code == 404
    unauthenticated = await client.post(door.url("/scan"), json={"payload": payload})
    assert unauthenticated.status_code == 401
    # The outsiders' attempts changed nothing.
    assert (await scan(client, door, payload))["result"] == "valid"


# --- undo ---------------------------------------------------------------------------------


async def test_undo_by_event_admin_and_owner_writes_audit_and_allows_rescan(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    ticket = door.tickets[0]
    await scan(client, door, ticket["qr_payload"])

    undone = await client.post(
        door.url(f"/tickets/{ticket['id']}/undo"),
        headers=bearer(door.admin),
        json={"reason": "Wrong person"},
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["ticket"]["status"] == "valid"
    assert undone.json()["stats"] == {"registered": 3, "checked_in": 0}

    record = await session.scalar(select(CheckInRecord))
    assert record is not None
    await session.refresh(record)
    assert record.reversed_at is not None
    assert record.reversed_by_user_id == door.admin.id
    assert record.reversal_reason == "Wrong person"
    entry = await session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action_type == "ticket.check_in_reversed")
    )
    assert entry is not None
    assert entry.actor_user_id == door.admin.id
    assert entry.event_id == door.event.id
    assert "Wrong person" in entry.description

    # The history keeps both records; the ticket can be admitted again.
    assert (await scan(client, door, ticket["qr_payload"]))["result"] == "valid"
    owner_undo = await client.post(
        door.url(f"/tickets/{ticket['id']}/undo"), headers=bearer(door.owner)
    )
    assert owner_undo.status_code == 200
    assert await session.scalar(select(func.count()).select_from(CheckInRecord)) == 2


async def test_check_in_staff_cannot_undo(client: httpx.AsyncClient, session: AsyncSession) -> None:
    door = await make_door(client, session)
    ticket = door.tickets[0]
    await scan(client, door, ticket["qr_payload"])
    response = await client.post(
        door.url(f"/tickets/{ticket['id']}/undo"), headers=bearer(door.staff)
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "checkin_undo_forbidden"
    assert (await scan(client, door, ticket["qr_payload"]))["result"] == "already_used"


async def test_undo_without_a_check_in(client: httpx.AsyncClient, session: AsyncSession) -> None:
    door = await make_door(client, session)
    other = await make_door(client, session)
    not_in = await client.post(
        door.url(f"/tickets/{door.tickets[0]['id']}/undo"), headers=bearer(door.admin)
    )
    assert (not_in.status_code, not_in.json()["error"]["code"]) == (409, "not_checked_in")
    foreign = await client.post(
        door.url(f"/tickets/{other.tickets[0]['id']}/undo"), headers=bearer(door.admin)
    )
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "ticket_not_found")


# --- manual search and counts -------------------------------------------------------------


async def test_manual_search_and_check_in(client: httpx.AsyncClient, session: AsyncSession) -> None:
    door = await make_door(client, session)

    async def find(q: str) -> list[str]:
        response = await client.get(
            door.url("/attendees"), headers=bearer(door.staff), params={"q": q}
        )
        assert response.status_code == 200, response.text
        return [t["attendee_name"] for t in response.json()["tickets"]]

    assert await find("aigerim") == ["Aigerim Bekova"]
    assert await find("SADYK") == ["Daniyar Sadykov"]
    assert await find("guest2@") == ["Ruslan 100%_Off"]
    assert await find(door.tickets[1]["ticket_number"].lower()) == ["Daniyar Sadykov"]
    # LIKE wildcards in the query are literal characters, not patterns.
    assert await find("%") == ["Ruslan 100%_Off"]
    assert await find("_") == ["Ruslan 100%_Off"]
    assert len(await find("")) == 3

    ticket_id = door.tickets[1]["id"]
    checked = await client.post(
        door.url(f"/tickets/{ticket_id}/check-in"), headers=bearer(door.staff)
    )
    assert checked.status_code == 200
    assert (checked.json()["result"], checked.json()["method"]) == ("valid", "manual_search")
    record = await session.scalar(select(CheckInRecord))
    assert record is not None
    assert record.method is CheckInMethod.MANUAL_SEARCH
    again = await client.post(
        door.url(f"/tickets/{ticket_id}/check-in"), headers=bearer(door.staff)
    )
    assert again.json()["result"] == "already_used"

    other = await make_door(client, session)
    foreign = await client.post(
        door.url(f"/tickets/{other.tickets[0]['id']}/check-in"), headers=bearer(door.staff)
    )
    assert (foreign.json()["result"], foreign.json()["reason"]) == ("invalid", "wrong_event")


async def test_stats_count_registered_and_checked_in(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session, names=("A One", "B Two", "C Three", "D Four"))
    await scan(client, door, door.tickets[0]["qr_payload"])
    await scan(client, door, door.tickets[1]["qr_payload"])
    await set_status(session, door.tickets[3]["id"], TicketStatus.REFUNDED)
    response = await client.get(door.url("/stats"), headers=bearer(door.staff))
    assert response.json() == {"registered": 3, "checked_in": 2}


# --- speed --------------------------------------------------------------------------------


async def test_checkin_under_2s(client: httpx.AsyncClient, session: AsyncSession) -> None:
    """SRS 7: "QR validation should normally complete within two seconds". Measured
    in-process against the test database, so this guards against slow queries, not network."""
    names = tuple(f"Guest {i:02d}" for i in range(30))
    door = await make_door(client, session, names=names)
    timings = []
    for ticket in door.tickets:
        started = time.perf_counter()
        body = await scan(client, door, ticket["qr_payload"])
        timings.append(time.perf_counter() - started)
        assert body["result"] == "valid"
    p95 = statistics.quantiles(timings, n=20)[-1]
    assert p95 < 2.0, f"p95 {p95:.3f}s"
    assert max(timings) < 2.0


# --- the organizer's attendee list --------------------------------------------------------


async def test_organizer_attendee_list_search_status_and_isolation(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    door = await make_door(client, session)
    await scan(client, door, door.tickets[0]["qr_payload"])
    await set_status(session, door.tickets[2]["id"], TicketStatus.REFUNDED)
    url = f"{API_PREFIX}/organizer/events/{door.event.id}/attendees"

    everyone = (await client.get(url, headers=bearer(door.owner))).json()
    assert [(a["attendee_name"], a["status"]) for a in everyone["attendees"]] == [
        ("Aigerim Bekova", "checked_in"),
        ("Daniyar Sadykov", "valid"),
        ("Ruslan 100%_Off", "refunded"),
    ]
    first = everyone["attendees"][0]
    assert first["attendee_email"] == "guest0@example.kz"
    assert first["order_reference"].startswith("BF-")
    assert first["checked_in_at"] is not None
    assert everyone["stats"] == {"registered": 2, "checked_in": 1}
    assert everyone["truncated"] is False

    by_ref = (
        await client.get(
            url, headers=bearer(door.owner), params={"q": first["order_reference"].lower()}
        )
    ).json()
    assert len(by_ref["attendees"]) == 3  # one order, three tickets
    refunded = (
        await client.get(url, headers=bearer(door.owner), params={"status": "refunded"})
    ).json()
    assert [a["attendee_name"] for a in refunded["attendees"]] == ["Ruslan 100%_Off"]
    bad = await client.get(url, headers=bearer(door.owner), params={"status": "lost"})
    assert bad.status_code == 422

    # Staff use the scanner's search; the organizer list is the owner's only.
    for outsider in (door.admin, door.staff):
        response = await client.get(url, headers=bearer(outsider))
        assert response.status_code in (403, 404)
    other = await make_door(client, session)
    assert (await client.get(url, headers=bearer(other.owner))).status_code == 404
