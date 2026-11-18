"""SRS 4.13 support cases: context from an event, order or ticket; who can see a case
(everyone else gets 404); the thread with internal notes; assignment; the four statuses;
organizer-to-platform cases; notifications and audit."""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventVisibility, StaffRole, UserRole
from app.main import API_PREFIX
from app.models import AuditLogEntry, Event, StaffAssignment, User
from app.services.mail import OutgoingEmail
from tests.factories import (
    bearer,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)

CASES = f"{API_PREFIX}/support/cases"


@dataclass
class World:
    event: Event
    owner: User
    event_admin: User
    scanner: User  # check-in staff: scans tickets, doesn't do support
    buyer: User
    order: dict[str, Any]
    admin: User  # platform admin
    stranger: User
    other_organizer: User


async def make_world(client: httpx.AsyncClient, session: AsyncSession, **event: Any) -> World:
    organizer = await make_organizer(session, locale="en")
    ev = await make_published_event(session, organizer, title="Student Tech Meetup", **event)
    tt = await make_ticket_type(session, ev)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    event_admin, scanner, buyer, stranger = [
        await make_user(session, locale="en") for _ in range(4)
    ]
    for user, role in ((event_admin, StaffRole.EVENT_ADMIN), (scanner, StaffRole.CHECK_IN_STAFF)):
        session.add(
            StaffAssignment(
                event_id=ev.id, user_id=user.id, role=role, assigned_by_user_id=owner.id
            )
        )
    admin = await make_user(session, role=UserRole.PLATFORM_ADMIN, locale="en")
    other = await make_organizer(session)
    other_organizer = await session.get(User, other.user_id)
    assert other_organizer is not None
    await session.commit()
    response = await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={"event_id": str(ev.id), "items": [{"ticket_type_id": str(tt.id), "quantity": 1}]},
    )
    assert response.status_code == 201, response.text
    return World(
        ev, owner, event_admin, scanner, buyer, response.json(), admin, stranger, other_organizer
    )


async def open_case(client: httpx.AsyncClient, user: User, **body: Any) -> httpx.Response:
    body.setdefault("category", "ticket_delivery")
    body.setdefault("subject", "I can't find my ticket")
    body.setdefault("message", "The email never arrived.")
    return await client.post(CASES, headers=bearer(user), json=body)


async def read(client: httpx.AsyncClient, user: User, case_id: str) -> httpx.Response:
    return await client.get(f"{CASES}/{case_id}", headers=bearer(user))


# --- opening a case with context -------------------------------------------------------------


async def test_case_from_a_ticket_carries_its_order_and_event(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    w = await make_world(client, session)
    mail.clear()
    ticket = w.order["tickets"][0]
    response = await open_case(client, w.buyer, ticket_id=ticket["id"])
    assert response.status_code == 201, response.text
    case = response.json()
    assert case["reference"].startswith("SC-")
    assert (case["kind"], case["status"], case["viewer_role"]) == ("attendee", "open", "requester")
    assert case["context"] == {
        "event_id": str(w.event.id),
        "event_title": "Student Tech Meetup",
        "event_slug": w.event.slug,
        "order_id": w.order["id"],
        "order_reference": w.order["reference"],
        "ticket_id": ticket["id"],
        "ticket_number": ticket["ticket_number"],
    }
    assert [m["body"] for m in case["messages"]] == ["The email never arrived."]
    assert case["can_manage"] is False and case["assignees"] == []
    # The organizer team hears about it (owner and event admin), not the scanner-only staff.
    assert sorted(m.to for m in mail) == sorted([w.owner.email, w.event_admin.email])
    assert {m.template for m in mail} == {"support_new_message"}


async def test_context_must_be_the_requesters_own(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    w = await make_world(client, session)
    for body, code in (
        ({"order_id": w.order["id"]}, "order_not_found"),
        ({"ticket_id": w.order["tickets"][0]["id"]}, "ticket_not_found"),
        ({"event_id": str(uuid.uuid4())}, "event_not_found"),
    ):
        response = await open_case(client, w.stranger, **body)
        assert (response.status_code, response.json()["error"]["code"]) == (404, code), body
    none = await open_case(client, w.stranger)
    assert (none.status_code, none.json()["error"]["code"]) == (422, "case_context_required")
    # Any visible event works on its own (a question before buying).
    assert (
        await open_case(client, w.stranger, event_id=str(w.event.id), category="event_information")
    ).status_code == 201


async def test_private_event_is_not_a_door_in(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    private = await make_published_event(session, organizer, visibility=EventVisibility.PRIVATE)
    outsider = await make_user(session)
    await session.commit()
    response = await open_case(client, outsider, event_id=str(private.id))
    assert (response.status_code, response.json()["error"]["code"]) == (404, "event_not_found")


# --- who sees a case --------------------------------------------------------------------------


async def test_only_participants_see_a_case(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    w = await make_world(client, session)
    case = (await open_case(client, w.buyer, order_id=w.order["id"])).json()

    for user, role in (
        (w.buyer, "requester"),
        (w.owner, "staff"),
        (w.event_admin, "staff"),
        (w.admin, "staff"),
    ):
        response = await read(client, user, case["id"])
        assert response.status_code == 200, user
        assert response.json()["viewer_role"] == role
    for outsider in (w.stranger, w.scanner, w.other_organizer):
        response = await read(client, outsider, case["id"])
        assert (response.status_code, response.json()["error"]["code"]) == (404, "case_not_found")
        reply = await client.post(
            f"{CASES}/{case['id']}/messages", headers=bearer(outsider), json={"body": "hi"}
        )
        assert reply.status_code == 404
        patch = await client.patch(
            f"{CASES}/{case['id']}", headers=bearer(outsider), json={"status": "resolved"}
        )
        assert patch.status_code == 404
        assert case["id"] not in [
            c["id"] for c in (await client.get(CASES, headers=bearer(outsider))).json()
        ]
    assert (await read(client, w.buyer, str(uuid.uuid4()))).status_code == 404

    for user in (w.buyer, w.owner, w.event_admin, w.admin):
        assert case["id"] in [
            c["id"] for c in (await client.get(CASES, headers=bearer(user))).json()
        ]


# --- the thread, assignment and statuses -----------------------------------------------------


async def test_thread_internal_notes_assignment_and_statuses(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    w = await make_world(client, session)
    case = (await open_case(client, w.buyer, order_id=w.order["id"], category="refund")).json()
    url = f"{CASES}/{case['id']}"
    mail.clear()

    # Staff assign the case and start on it: the assignee and the requester are told.
    managed = await client.patch(
        url,
        headers=bearer(w.owner),
        json={"assigned_to_user_id": str(w.event_admin.id), "status": "in_progress"},
    )
    assert managed.status_code == 200, managed.text
    body = managed.json()
    assert body["assigned_to"]["id"] == str(w.event_admin.id)
    assert body["status"] == "in_progress"
    assert body["can_manage"] is True
    assert {p["id"] for p in body["assignees"]} == {str(w.owner.id), str(w.event_admin.id)}
    assert sorted((m.to, m.template) for m in mail) == sorted(
        [(w.event_admin.email, "support_case_assigned"), (w.buyer.email, "support_status_changed")]
    )
    mail.clear()

    # An internal note stays on the staff side; a reply reaches the requester.
    note = await client.post(
        f"{url}/messages",
        headers=bearer(w.event_admin),
        json={"body": "Check payment logs", "internal": True},
    )
    assert note.status_code == 201
    assert mail == []
    answer = await client.post(
        f"{url}/messages",
        headers=bearer(w.event_admin),
        json={"body": "Can you confirm your email?"},
    )
    assert answer.status_code == 201
    assert [(m.to, m.template) for m in mail] == [(w.buyer.email, "support_new_message")]
    await client.patch(url, headers=bearer(w.event_admin), json={"status": "waiting_for_customer"})

    seen_by_requester = (await read(client, w.buyer, case["id"])).json()
    assert [m["body"] for m in seen_by_requester["messages"]] == [
        "The email never arrived.",
        "Can you confirm your email?",
    ]
    assert [m["from_staff"] for m in seen_by_requester["messages"]] == [False, True]
    seen_by_staff = (await read(client, w.owner, case["id"])).json()
    assert [m["internal"] for m in seen_by_staff["messages"]] == [False, True, False]

    # The requester can't post notes or change the case.
    sneaky = await client.post(
        f"{url}/messages", headers=bearer(w.buyer), json={"body": "x", "internal": True}
    )
    assert sneaky.status_code == 403
    forbidden = await client.patch(url, headers=bearer(w.buyer), json={"status": "resolved"})
    assert forbidden.status_code == 403

    # The requester's reply puts it back in progress and reaches the assignee only.
    mail.clear()
    replied = await client.post(
        f"{url}/messages", headers=bearer(w.buyer), json={"body": "Yes, it's right."}
    )
    assert replied.json()["status"] == "in_progress"
    assert [(m.to, m.template) for m in mail] == [(w.event_admin.email, "support_new_message")]

    resolved = await client.patch(url, headers=bearer(w.event_admin), json={"status": "resolved"})
    assert resolved.json()["status"] == "resolved" and resolved.json()["resolved_at"] is not None
    reopened = await client.post(
        f"{url}/messages", headers=bearer(w.buyer), json={"body": "It happened again."}
    )
    assert reopened.json()["status"] == "open" and reopened.json()["resolved_at"] is None

    bad = await client.patch(
        url, headers=bearer(w.owner), json={"assigned_to_user_id": str(w.stranger.id)}
    )
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "invalid_assignee")
    unassigned = await client.patch(
        url, headers=bearer(w.owner), json={"assigned_to_user_id": None}
    )
    assert unassigned.json()["assigned_to"] is None

    # SRS 4.16: status changes are on the event's timeline.
    changes = list(
        await session.scalars(
            select(AuditLogEntry.description).where(
                AuditLogEntry.action_type == "support_case.status_changed",
                AuditLogEntry.event_id == w.event.id,
            )
        )
    )
    assert len(changes) == 5


# --- organizer-to-platform cases -------------------------------------------------------------


async def test_organizer_cases_go_to_the_platform(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    w = await make_world(client, session)
    mail.clear()
    response = await open_case(
        client,
        w.owner,
        kind="organizer",
        category="payment",
        subject="Activation fee",
        event_id=str(w.event.id),
    )
    assert response.status_code == 201, response.text
    case = response.json()
    assert case["kind"] == "organizer"
    assert [m.to for m in mail] == [w.admin.email]

    assert (await read(client, w.admin, case["id"])).json()["can_manage"] is True
    # The organizer's own event admin and other organizers don't see it.
    for outsider in (w.event_admin, w.other_organizer, w.buyer):
        assert (await read(client, outsider, case["id"])).status_code == 404
    answer = await client.post(
        f"{CASES}/{case['id']}/messages", headers=bearer(w.admin), json={"body": "Looking into it."}
    )
    assert answer.status_code == 201
    assert (
        await client.patch(
            f"{CASES}/{case['id']}", headers=bearer(w.owner), json={"status": "resolved"}
        )
    ).status_code == 403

    attendee_try = await open_case(client, w.buyer, kind="organizer", category="account")
    assert attendee_try.status_code == 403
    foreign = await open_case(client, w.other_organizer, kind="organizer", event_id=str(w.event.id))
    assert foreign.status_code == 404
    general = await open_case(client, w.other_organizer, kind="organizer", category="technical")
    assert general.status_code == 201  # no event needed for account or technical questions
