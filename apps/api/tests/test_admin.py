"""SRS 4.12 platform administration: Platform Admins only; search; suspend users, events and
paid sales (taking effect on the next request); activation records; the activation fee as a
runtime setting; reported events; CSV export; every action audited."""

import csv
import io
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserRole
from app.main import API_PREFIX
from app.models import AuditLogEntry, Event, TicketType, User
from tests.factories import (
    bearer,
    enable_paid_sales,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)

ADMIN = f"{API_PREFIX}/admin"


async def admin_user(session: AsyncSession) -> User:
    return await make_user(session, role=UserRole.PLATFORM_ADMIN)


async def shop(session: AsyncSession) -> tuple[Event, TicketType, TicketType, User]:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer, title="Almaty Jazz Night")
    paid = await make_ticket_type(session, event, price_kzt=8000)
    free = await make_ticket_type(session, event, price_kzt=0)
    await enable_paid_sales(session, event)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    return event, paid, free, owner


async def buy(
    client: httpx.AsyncClient, user: User, event: Event, tt: TicketType
) -> httpx.Response:
    return await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(user),
        json={"event_id": str(event.id), "items": [{"ticket_type_id": str(tt.id), "quantity": 1}]},
    )


async def actions(session: AsyncSession) -> list[str]:
    return list(
        await session.scalars(select(AuditLogEntry.action_type).order_by(AuditLogEntry.occurred_at))
    )


async def test_only_platform_admins(client: httpx.AsyncClient, session: AsyncSession) -> None:
    organizer = await make_organizer(session)
    owner = await session.get(User, organizer.user_id)
    attendee = await make_user(session)
    await session.commit()
    assert owner is not None
    for path in (
        "/summary",
        "/users",
        "/events",
        "/orders",
        "/payments",
        "/activations",
        "/reports",
        "/settings",
        "/export/users.csv",
    ):
        for user in (owner, attendee):
            response = await client.get(f"{ADMIN}{path}", headers=bearer(user))
            assert response.status_code == 403, (path, response.text)
        assert (await client.get(f"{ADMIN}{path}")).status_code == 401
    put = await client.put(
        f"{ADMIN}/settings", headers=bearer(owner), json={"activation_fee_kzt": 1}
    )
    assert put.status_code == 403


async def test_search_and_suspend_users(client: httpx.AsyncClient, session: AsyncSession) -> None:
    admin = await admin_user(session)
    target = await make_user(session, full_name="Suspicious Sam")
    other_admin = await admin_user(session)
    await session.commit()
    token = bearer(target)

    found = (
        await client.get(f"{ADMIN}/users", headers=bearer(admin), params={"q": "suspicious"})
    ).json()
    assert [u["id"] for u in found["items"]] == [str(target.id)]
    by_role = (
        await client.get(f"{ADMIN}/users", headers=bearer(admin), params={"role": "platform_admin"})
    ).json()
    assert {u["id"] for u in by_role["items"]} == {str(admin.id), str(other_admin.id)}

    suspended = await client.post(
        f"{ADMIN}/users/{target.id}/suspend",
        headers=bearer(admin),
        json={"reason": "Chargeback fraud"},
    )
    assert suspended.status_code == 200 and suspended.json()["is_suspended"] is True
    # Their existing token stops working on the next request; signing in fails.
    me = await client.get(f"{API_PREFIX}/me", headers=token)
    assert (me.status_code, me.json()["error"]["code"]) == (403, "account_suspended")
    assert "admin.user_suspended" in await actions(session)

    assert (
        await client.post(f"{ADMIN}/users/{target.id}/unsuspend", headers=bearer(admin))
    ).json()["is_suspended"] is False
    assert (await client.get(f"{API_PREFIX}/me", headers=token)).status_code == 200

    no_reason = await client.post(
        f"{ADMIN}/users/{target.id}/suspend", headers=bearer(admin), json={"reason": ""}
    )
    assert no_reason.status_code == 422
    protected = await client.post(
        f"{ADMIN}/users/{other_admin.id}/suspend", headers=bearer(admin), json={"reason": "nope"}
    )
    assert (protected.status_code, protected.json()["error"]["code"]) == (
        409,
        "cannot_suspend_admin",
    )
    assert (
        await client.post(
            f"{ADMIN}/users/{uuid.uuid4()}/suspend", headers=bearer(admin), json={"reason": "who"}
        )
    ).status_code == 404


async def test_suspending_an_event_stops_sales_at_once(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    admin = await admin_user(session)
    event, _, free, _ = await shop(session)
    buyer = await make_user(session)
    await session.commit()
    assert (await buy(client, buyer, event, free)).status_code == 201

    response = await client.post(
        f"{ADMIN}/events/{event.id}/suspend",
        headers=bearer(admin),
        json={"reason": "Reported as fake"},
    )
    assert response.status_code == 200 and response.json()["is_suspended"] is True
    blocked = await buy(client, buyer, event, free)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "sales_suspended")
    listed = (await client.get(f"{API_PREFIX}/events")).json()
    assert str(event.id) not in [e["id"] for e in listed["items"]]
    entry = await session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action_type == "admin.event_suspended")
    )
    assert (
        entry is not None and entry.event_id == event.id and "Reported as fake" in entry.description
    )

    await client.post(f"{ADMIN}/events/{event.id}/unsuspend", headers=bearer(admin))
    assert (await buy(client, buyer, event, free)).status_code == 201
    searched = (
        await client.get(f"{ADMIN}/events", headers=bearer(admin), params={"q": "jazz"})
    ).json()
    assert searched["items"][0]["paid_sales"] == "active"


async def test_suspending_paid_sales_stops_paid_checkout_only(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    admin = await admin_user(session)
    event, paid, free, _ = await shop(session)
    buyer = await make_user(session)
    await session.commit()

    response = await client.post(
        f"{ADMIN}/events/{event.id}/paid-sales/suspend",
        headers=bearer(admin),
        json={"reason": "Fraud suspected"},
    )
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["suspended_reason"]) == (
        "suspended",
        "Fraud suspected",
    )
    paid_try = await buy(client, buyer, event, paid)
    assert (paid_try.status_code, paid_try.json()["error"]["code"]) == (
        409,
        "paid_sales_not_active",
    )
    assert (await buy(client, buyer, event, free)).status_code == 201

    records = (
        await client.get(
            f"{ADMIN}/activations", headers=bearer(admin), params={"status": "suspended"}
        )
    ).json()
    assert [r["event_id"] for r in records["items"]] == [str(event.id)]

    resumed = await client.post(
        f"{ADMIN}/events/{event.id}/paid-sales/resume", headers=bearer(admin)
    )
    assert resumed.json()["status"] == "active"
    assert (await buy(client, buyer, event, paid)).status_code == 201
    assert {"admin.paid_sales_suspended", "admin.paid_sales_resumed"} <= set(await actions(session))


async def test_activation_fee_is_a_runtime_setting(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    admin = await admin_user(session)
    organizer = await make_organizer(session)
    owner = await session.get(User, organizer.user_id)
    assert owner is not None
    event = await make_published_event(session, organizer)
    await make_ticket_type(session, event, price_kzt=5000)
    await session.commit()

    default = (await client.get(f"{ADMIN}/settings", headers=bearer(admin))).json()
    assert (default["activation_fee_kzt"], default["customized"]) == (5000, False)

    changed = await client.put(
        f"{ADMIN}/settings", headers=bearer(admin), json={"activation_fee_kzt": 7500}
    )
    assert changed.status_code == 200 and changed.json() == {
        **changed.json(),
        "activation_fee_kzt": 7500,
        "customized": True,
    }
    checklist = (
        await client.get(
            f"{API_PREFIX}/organizer/events/{event.id}/activation", headers=bearer(owner)
        )
    ).json()
    assert checklist["activation_fee_kzt"] == 7500
    paid = await client.post(
        f"{API_PREFIX}/organizer/events/{event.id}/activation/fee-payment",
        headers={**bearer(owner), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "succeed"},
    )
    assert paid.status_code in (200, 201), paid.text
    assert paid.json()["activation_payment"]["amount_kzt"] == 7500
    # Later changes don't rewrite fees already paid.
    await client.put(f"{ADMIN}/settings", headers=bearer(admin), json={"activation_fee_kzt": 9000})
    again = (
        await client.get(
            f"{API_PREFIX}/organizer/events/{event.id}/activation", headers=bearer(owner)
        )
    ).json()
    assert again["activation_fee_kzt"] == 7500
    assert (
        await client.put(
            f"{ADMIN}/settings", headers=bearer(admin), json={"activation_fee_kzt": -1}
        )
    ).status_code == 422
    assert (await actions(session)).count("admin.activation_fee_changed") == 2


async def test_reported_events_are_reviewed(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    admin = await admin_user(session)
    event, _, free, _ = await shop(session)
    reporter, second = await make_user(session), await make_user(session)
    await session.commit()
    url = f"{API_PREFIX}/events/{event.slug}/report"

    first = await client.post(
        url,
        headers=bearer(reporter),
        json={"reason": "fraud", "details": "Same event posted twice"},
    )
    assert first.status_code == 201 and first.json()["status"] == "open"
    dup = await client.post(url, headers=bearer(reporter), json={"reason": "spam"})
    assert (dup.status_code, dup.json()["error"]["code"]) == (409, "report_already_open")
    assert (await client.post(url, json={"reason": "spam"})).status_code == 401
    assert (
        await client.post(
            f"{API_PREFIX}/events/no-such-event/report",
            headers=bearer(reporter),
            json={"reason": "spam"},
        )
    ).status_code == 404
    other = await client.post(url, headers=bearer(second), json={"reason": "misleading"})

    queue = (
        await client.get(f"{ADMIN}/reports", headers=bearer(admin), params={"status": "open"})
    ).json()
    assert {r["id"] for r in queue["items"]} == {first.json()["id"], other.json()["id"]}
    assert (await client.get(f"{ADMIN}/events", headers=bearer(admin))).json()["items"][0][
        "open_reports"
    ] == 2

    dismissed = await client.post(
        f"{ADMIN}/reports/{other.json()['id']}/review",
        headers=bearer(admin),
        json={"action": "dismiss", "note": "Fine"},
    )
    assert dismissed.json()["status"] == "dismissed"
    actioned = await client.post(
        f"{ADMIN}/reports/{first.json()['id']}/review",
        headers=bearer(admin),
        json={"action": "suspend_event"},
    )
    assert (actioned.json()["status"], actioned.json()["event_suspended"]) == ("actioned", True)
    assert (await buy(client, reporter, event, free)).json()["error"]["code"] == "sales_suspended"
    twice = await client.post(
        f"{ADMIN}/reports/{first.json()['id']}/review",
        headers=bearer(admin),
        json={"action": "dismiss"},
    )
    assert twice.status_code == 409
    # Their earlier report was reviewed, so they may report again (a suspended event can
    # still be opened by its link; it just can't sell).
    assert (
        await client.post(url, headers=bearer(second), json={"reason": "other"})
    ).status_code == 201
    assert {"admin.report_dismissed", "admin.report_actioned", "admin.event_suspended"} <= set(
        await actions(session)
    )


async def test_orders_payments_and_summary(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    admin = await admin_user(session)
    event, paid, _, _ = await shop(session)
    buyer = await make_user(session, email="buyer-search@example.kz")
    await session.commit()
    order = (await buy(client, buyer, event, paid)).json()
    await client.post(
        f"{API_PREFIX}/orders/{order['id']}/payments",
        headers={**bearer(buyer), "Idempotency-Key": str(uuid.uuid4())},
        json={"outcome": "fail"},
    )
    orders = (
        await client.get(f"{ADMIN}/orders", headers=bearer(admin), params={"q": order["reference"]})
    ).json()
    assert [(o["reference"], o["status"]) for o in orders["items"]] == [
        (order["reference"], "failed")
    ]
    failed = (
        await client.get(f"{ADMIN}/payments", headers=bearer(admin), params={"status": "failed"})
    ).json()
    (payment,) = failed["items"]
    assert (payment["user_email"], payment["order_reference"], payment["demo"]) == (
        "buyer-search@example.kz",
        order["reference"],
        True,
    )
    assert payment["event_title"] == "Almaty Jazz Night"
    summary = (await client.get(f"{ADMIN}/summary", headers=bearer(admin))).json()
    assert summary["payments_failed"] == 1 and summary["events_published"] >= 1


async def test_csv_export_is_safe_and_audited(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    admin = await admin_user(session)
    await make_user(session, full_name='=HYPERLINK("http://evil","x")', email="formula@example.kz")
    await shop(session)
    await session.commit()

    response = await client.get(f"{ADMIN}/export/users.csv", headers=bearer(admin))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="biletflow-users.csv"' in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    evil = next(r for r in rows if r["email"] == "formula@example.kz")
    assert evil["full_name"].startswith("'=")  # not run as a formula by spreadsheets
    for kind in ("events", "orders", "payments"):
        assert (
            await client.get(f"{ADMIN}/export/{kind}.csv", headers=bearer(admin))
        ).status_code == 200
    assert (
        await client.get(f"{ADMIN}/export/secrets.csv", headers=bearer(admin))
    ).status_code == 422
    assert (await actions(session)).count("admin.exported") == 4
