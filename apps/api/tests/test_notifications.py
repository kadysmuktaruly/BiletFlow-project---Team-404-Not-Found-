"""SRS 4.10 notifications: one interface, email plus in-app, kk/ru/en templates, every
trigger that exists so far, and the inbox API."""

import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, NotificationChannel, NotificationType, TicketStatus
from app.i18n.emails import EMAILS
from app.main import API_PREFIX
from app.models import Event, Notification, Ticket, TicketType, User
from app.services.mail import OutgoingEmail
from app.services.notifications import Message, notify
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)

INBOX = f"{API_PREFIX}/me/notifications"


async def free_event(session: AsyncSession) -> tuple[Event, TicketType, User]:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer, title="Student Tech Meetup")
    tt = await make_ticket_type(session, event, name="Free entry")
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    await session.commit()
    return event, tt, owner


async def register(
    client: httpx.AsyncClient, event: Event, tt: TicketType, buyer: User, n: int = 1
) -> dict[str, Any]:
    response = await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={
            "event_id": str(event.id),
            "items": [{"ticket_type_id": str(tt.id), "quantity": n}],
            "attendees": [{"full_name": f"Guest {i}"} for i in range(n)],
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def inbox(client: httpx.AsyncClient, user: User, **params: Any) -> dict[str, Any]:
    response = await client.get(INBOX, headers=bearer(user), params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# --- the interface --------------------------------------------------------------------------


async def test_notify_writes_email_and_in_app_in_the_users_language(session: AsyncSession) -> None:
    user = await make_user(session, locale="ru", full_name="Айгерим")
    outbound = await notify(
        session,
        user,
        Message(
            type=NotificationType.REFUND_COMPLETED,
            template="refund_completed",
            params={"event": "Джаз", "reference": "BF-ABC234", "amount": "8 000 KZT"},
            action_path="/orders/123",
        ),
    )
    await session.commit()
    (msg, notification_id) = outbound[0]
    assert msg.subject == "DEMO-возврат выполнен: Джаз"
    assert "Айгерим" in msg.text
    assert "http://localhost:3000/ru/orders/123" in msg.text
    rows = list(await session.scalars(select(Notification).where(Notification.user_id == user.id)))
    by_channel = {n.channel: n for n in rows}
    assert set(by_channel) == {NotificationChannel.EMAIL, NotificationChannel.IN_APP}
    in_app = by_channel[NotificationChannel.IN_APP]
    assert in_app.subject == msg.subject
    assert "BF-ABC234" in in_app.body and "8 000 KZT" in in_app.body
    assert in_app.action_path == "/orders/123"
    assert by_channel[NotificationChannel.EMAIL].id == notification_id


async def test_channels_can_be_chosen(session: AsyncSession) -> None:
    user = await make_user(session)
    only_in_app = await notify(
        session,
        user,
        Message(
            type=NotificationType.SUPPORT_NEW_MESSAGE,
            template="support_new_message",
            params={"reference": "SC-1", "subject": "Hi"},
            email=False,
        ),
    )
    assert only_in_app == []
    rows = list(
        await session.scalars(select(Notification.channel).where(Notification.user_id == user.id))
    )
    assert rows == [NotificationChannel.IN_APP]


def test_every_template_exists_in_kk_ru_en_with_the_same_placeholders() -> None:
    def placeholders(tpl: dict[str, Any]) -> set[str]:
        texts = [v for v in tpl.values() if isinstance(v, str)] + list(tpl.get("paragraphs", []))
        return {name for text in texts for _, name, _, _ in string.Formatter().parse(text) if name}

    for name, by_locale in EMAILS.items():
        assert set(by_locale) == {"kk", "ru", "en"}, name
        shapes = {loc: placeholders(dict(tpl)) for loc, tpl in by_locale.items()}
        assert shapes["kk"] == shapes["ru"] == shapes["en"], name
        keys = {loc: set(tpl) for loc, tpl in by_locale.items()}
        assert keys["kk"] == keys["ru"] == keys["en"], name
    for template in ("payment_failed", "refund_completed", "payout_status"):
        for tpl in EMAILS[template].values():
            assert "DEMO" in tpl["subject"] + " ".join(tpl.get("paragraphs", [])), template


# --- triggers -----------------------------------------------------------------------------


async def test_registration_is_emailed_and_shown_in_app(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, _ = await free_event(session)
    buyer = await make_user(session, locale="en")
    await session.commit()
    order = await register(client, event, tt, buyer)

    body = await inbox(client, buyer)
    assert body["unread_count"] == 1
    (item,) = body["items"]
    assert item["type"] == "registration_confirmation"
    assert item["subject"] == "Your tickets: Student Tech Meetup"
    assert order["reference"] in item["body"]
    assert item["action_path"] == "/tickets"
    assert item["order_id"] == order["id"]
    assert [m.template for m in mail] == ["order_confirmed"]


async def test_payment_failure_is_shown_in_app(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer, title="Jazz")
    tt = await make_ticket_type(session, event, price_kzt=5000)
    await enable_paid_sales(session, event)
    buyer = await make_user(session, locale="en")
    await session.commit()
    order = await register(client, event, tt, buyer)
    await client.post(
        f"{API_PREFIX}/orders/{order['id']}/payments",
        headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "fail"},
    )
    (item,) = (await inbox(client, buyer))["items"]
    assert (item["type"], item["subject"]) == ("payment_failure", "DEMO payment failed: Jazz")


async def test_event_changes_notify_each_ticket_holder_once(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, owner = await free_event(session)
    two_tickets, one_ticket, refunded = [await make_user(session, locale="en") for _ in range(3)]
    await session.commit()
    await register(client, event, tt, two_tickets, n=2)
    await register(client, event, tt, one_ticket)
    gone = await register(client, event, tt, refunded)
    await session.execute(
        update(Ticket)
        .where(Ticket.order_id == uuid.UUID(gone["id"]))
        .values(status=TicketStatus.REFUNDED)
    )
    await session.commit()
    mail.clear()
    url = f"{API_PREFIX}/organizer/events/{event.id}"

    # A description edit isn't material: nobody is told.
    await client.patch(url, headers=bearer(owner), json={"description": "Bring a laptop."})
    assert mail == []

    later = (datetime.now(UTC) + timedelta(days=20)).replace(microsecond=0)
    response = await client.patch(
        url,
        headers=bearer(owner),
        json={"starts_at": later.isoformat(), "ends_at": (later + timedelta(hours=3)).isoformat()},
    )
    assert response.status_code == 200, response.text
    assert sorted(m.to for m in mail) == sorted([two_tickets.email, one_ticket.email])
    assert {m.template for m in mail} == {"event_updated"}
    (item,) = (await inbox(client, one_ticket, unread_only=True))["items"][:1]
    assert item["type"] == "event_update"
    assert "time" in item["body"]
    assert item["action_path"] == f"/events/{event.slug}"
    assert all(i["type"] != "event_update" for i in (await inbox(client, refunded))["items"])


async def test_drafts_never_notify(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    organizer = await make_organizer(session)
    draft = await make_published_event(session, organizer, status=EventStatus.DRAFT)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    await session.commit()
    await client.patch(
        f"{API_PREFIX}/organizer/events/{draft.id}",
        headers=bearer(owner),
        json={"title": "Renamed"},
    )
    assert mail == []


async def test_cancellation_notifies_ticket_holders(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    event, tt, owner = await free_event(session)
    holders = [await make_user(session, locale=loc) for loc in ("kk", "en")]
    await session.commit()
    for holder in holders:
        await register(client, event, tt, holder)
    mail.clear()

    response = await client.post(
        f"{API_PREFIX}/organizer/events/{event.id}/cancel",
        headers=bearer(owner),
        json={"reason": "Venue flooded"},
    )
    assert response.status_code == 200
    assert sorted(m.to for m in mail) == sorted(h.email for h in holders)
    subjects = {m.to: m.subject for m in mail}
    assert subjects[holders[0].email] == "Іс-шара тоқтатылды: Student Tech Meetup"
    assert subjects[holders[1].email] == "Event cancelled: Student Tech Meetup"
    (latest, *_) = (await inbox(client, holders[1]))["items"]
    assert (latest["type"], latest["action_path"]) == ("event_cancellation", "/orders")


async def test_payout_account_status_is_notified(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    organizer = await make_organizer(session, locale="en")
    user = await session.get(User, organizer.user_id)
    assert user is not None
    await session.commit()
    response = await client.put(
        f"{API_PREFIX}/organizer/payout-account",
        headers=bearer(user),
        json={
            "account_holder_name": "Aruzhan S",
            "bank_name": "Demo Bank",
            "account_last4": "4242",
        },
    )
    assert response.status_code == 200, response.text
    (item,) = (await inbox(client, user))["items"]
    assert item["type"] == "payout_status"
    assert item["subject"] == "Payout account: verified"
    assert "4242" in item["body"] and "DEMO" in item["body"]
    assert [m.template for m in mail] == ["payout_status"]


# --- the inbox ----------------------------------------------------------------------------


async def test_inbox_read_state_and_privacy(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event, tt, _ = await free_event(session)
    me, other = await make_user(session), await make_user(session)
    await session.commit()
    for _ in range(3):
        await register(client, event, tt, me)
    await register(client, event, tt, other)

    body = await inbox(client, me)
    assert (len(body["items"]), body["unread_count"]) == (3, 3)
    first = body["items"][0]["id"]
    assert (await client.get(f"{INBOX}/unread-count", headers=bearer(me))).json() == {
        "unread_count": 3
    }

    read = await client.post(f"{INBOX}/{first}/read", headers=bearer(me))
    assert read.status_code == 200 and read.json()["read_at"] is not None
    assert (await inbox(client, me))["unread_count"] == 2
    assert len((await inbox(client, me, unread_only="true"))["items"]) == 2

    # Someone else's notification doesn't exist for you.
    other_id = (await inbox(client, other))["items"][0]["id"]
    assert (await client.post(f"{INBOX}/{other_id}/read", headers=bearer(me))).status_code == 404
    assert (
        await client.post(f"{INBOX}/{uuid.uuid4()}/read", headers=bearer(me))
    ).status_code == 404

    assert (await client.post(f"{INBOX}/read-all", headers=bearer(me))).status_code == 204
    assert (await inbox(client, me))["unread_count"] == 0
    assert (await inbox(client, other))["unread_count"] == 1
    assert (await client.get(INBOX)).status_code == 401
    # Only in-app rows are listed, never the email copies.
    emails = await session.scalar(
        select(Notification.id).where(
            Notification.user_id == me.id, Notification.channel == NotificationChannel.EMAIL
        )
    )
    assert emails is not None
    assert all(item["id"] != str(emails) for item in (await inbox(client, me))["items"])
