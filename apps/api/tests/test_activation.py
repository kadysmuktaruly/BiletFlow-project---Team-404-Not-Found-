"""SRS 3.2 / 4.5 / UC2: the paid-sales activation checklist, all simulated."""

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import API_PREFIX
from app.models import AuditLogEntry, Event, OrganizerProfile, Payment
from tests.factories import (
    bearer,
    make_event,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
    organizer_bearer,
)


def _url(event: Event, step: str = "") -> str:
    return f"{API_PREFIX}/organizer/events/{event.id}/activation{step}"


async def _setup(session: AsyncSession) -> tuple[OrganizerProfile, Event, dict[str, str]]:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer)
    await session.commit()
    return organizer, event, await organizer_bearer(session, organizer)


async def test_checklist_starts_empty_with_fee_from_settings(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _setup(session)
    body = (await client.get(_url(event), headers=headers)).json()
    assert body["status"] == "not_started"
    assert body["paid_sales_enabled"] is False
    assert body["activation_fee_kzt"] == 5000  # ACTIVATION_FEE_KZT default
    assert body["fee_refundable"] is False
    assert body["demo"] is True
    for step in (
        "has_paid_ticket_type",
        "identity_verified",
        "payout_account_connected",
        "activation_fee_paid",
        "terms_accepted",
    ):
        assert body[step] is False


async def test_full_checklist_enables_paid_checkout(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _setup(session)
    paid = await make_ticket_type(session, event, price_kzt=5000)
    buyer = await make_user(session)
    await session.commit()
    order_body = {
        "event_id": str(event.id),
        "items": [{"ticket_type_id": str(paid.id), "quantity": 1}],
    }

    payout_first = await client.post(
        _url(event, "/payout-account"), headers=headers, json={"confirm": True}
    )
    assert payout_first.status_code == 409
    assert payout_first.json()["error"]["code"] == "payout_account_required"
    await client.put(
        f"{API_PREFIX}/organizer/payout-account",
        headers=headers,
        json={"account_holder_name": "A", "bank_name": "Kaspi", "account_last4": "1234"},
    )

    steps = [
        ("/identity", {"confirm": True}),
        ("/payout-account", {"confirm": True}),
        ("/terms", {"confirm": True}),
    ]
    for path, body in steps:
        response = await client.post(_url(event, path), headers=headers, json=body)
        assert response.status_code == 200, path
        assert response.json()["status"] == "in_progress"
        blocked = await client.post(f"{API_PREFIX}/orders", headers=bearer(buyer), json=order_body)
        assert blocked.json()["error"]["code"] == "paid_sales_not_active"

    failed_fee = await client.post(
        _url(event, "/fee-payment"),
        headers={**headers, "Idempotency-Key": f"fee-{uuid.uuid4()}"},
        json={"outcome": "fail"},
    )
    assert failed_fee.json()["activation_fee_paid"] is False

    key = f"fee-{uuid.uuid4()}"
    fee = await client.post(
        _url(event, "/fee-payment"),
        headers={**headers, "Idempotency-Key": key},
        json={"outcome": "succeed"},
    )
    body = fee.json()
    assert body["status"] == "active"
    assert body["paid_sales_enabled"] is True
    assert body["activation_payment"]["amount_kzt"] == 5000
    assert body["activation_payment"]["purpose"] == "activation_fee"
    assert body["activation_payment"]["demo"] is True

    replay = await client.post(
        _url(event, "/fee-payment"),
        headers={**headers, "Idempotency-Key": key},
        json={"outcome": "succeed"},
    )
    assert replay.status_code == 200
    payments = list(await session.scalars(select(Payment).where(Payment.event_id == event.id)))
    assert len(payments) == 2  # one failed attempt, one success; the replay added nothing

    assert (
        await client.post(f"{API_PREFIX}/orders", headers=bearer(buyer), json=order_body)
    ).status_code == 201
    actions = set(
        await session.scalars(
            select(AuditLogEntry.action_type).where(AuditLogEntry.event_id == event.id)
        )
    )
    assert {
        "activation.identity_verified",
        "activation.terms_accepted",
        "activation.activated",
    } <= actions


async def test_activation_needs_a_paid_ticket_type(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_event(session, organizer)
    await make_ticket_type(session, event, price_kzt=0)
    await session.commit()
    headers = await organizer_bearer(session, organizer)
    await client.put(
        f"{API_PREFIX}/organizer/payout-account",
        headers=headers,
        json={"account_holder_name": "A", "bank_name": "Kaspi", "account_last4": "1234"},
    )
    for path in ("/identity", "/payout-account", "/terms"):
        await client.post(_url(event, path), headers=headers, json={"confirm": True})
    body = (
        await client.post(
            _url(event, "/fee-payment"),
            headers={**headers, "Idempotency-Key": f"fee-{uuid.uuid4()}"},
            json={"outcome": "succeed"},
        )
    ).json()
    assert body["has_paid_ticket_type"] is False
    assert body["status"] == "in_progress"

    await make_ticket_type(session, event, price_kzt=1000)
    await session.commit()
    assert (await client.get(_url(event), headers=headers)).json()["status"] == "active"


async def test_activation_is_per_event_and_owner_only(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer, event, headers = await _setup(session)
    other_event = await make_published_event(session, organizer)
    stranger = await make_organizer(session)
    await session.commit()
    await client.post(_url(event, "/identity"), headers=headers, json={"confirm": True})
    assert (await client.get(_url(other_event), headers=headers)).json()[
        "identity_verified"
    ] is False
    response = await client.get(_url(event), headers=await organizer_bearer(session, stranger))
    assert response.status_code == 404


async def test_confirm_steps_require_true(client: httpx.AsyncClient, session: AsyncSession) -> None:
    _, event, headers = await _setup(session)
    response = await client.post(_url(event, "/terms"), headers=headers, json={"confirm": False})
    assert response.status_code == 422
