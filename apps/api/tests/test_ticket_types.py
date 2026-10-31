"""SRS 4.3: organizers manage free and paid ticket types."""

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import API_PREFIX
from app.models import AuditLogEntry, Event, OrganizerProfile
from tests.factories import (
    bearer,
    make_event,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
    organizer_bearer,
)


def _url(event: Event, suffix: str = "") -> str:
    return f"{API_PREFIX}/organizer/events/{event.id}/ticket-types{suffix}"


async def _setup(session: AsyncSession) -> tuple[OrganizerProfile, Event, dict[str, str]]:
    organizer = await make_organizer(session)
    event = await make_event(session, organizer)
    await session.commit()
    return organizer, event, await organizer_bearer(session, organizer)


def _body(**overrides: Any) -> dict[str, Any]:
    return {"name": "Standard", "price_kzt": 5000, "quantity_total": 100, **overrides}


async def test_create_free_and_paid_types_with_counts(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _setup(session)
    free = await client.post(_url(event), headers=headers, json=_body(name="Student", price_kzt=0))
    paid = await client.post(
        _url(event),
        headers=headers,
        json=_body(max_per_order=4, sales_start_at="2026-12-01T10:00", is_hidden=True),
    )
    assert free.status_code == paid.status_code == 201
    assert free.json()["is_free"] is True
    body = paid.json()
    assert body["is_free"] is False
    assert body["max_per_order"] == 4
    assert body["is_hidden"] is True
    # 10:00 Almaty is 05:00 UTC
    assert datetime.fromisoformat(body["sales_start_at"]) == datetime(2026, 12, 1, 5, tzinfo=UTC)
    for key in (
        "quantity_available",
        "quantity_sold",
        "quantity_reserved",
        "quantity_refunded",
        "quantity_checked_in",
    ):
        assert key in body
    assert body["quantity_available"] == 100

    listed = await client.get(_url(event), headers=headers)
    assert [t["name"] for t in listed.json()] == ["Student", "Standard"]


async def test_create_validation(client: httpx.AsyncClient, session: AsyncSession) -> None:
    _, event, headers = await _setup(session)
    assert (
        await client.post(_url(event), headers=headers, json=_body(price_kzt=-1))
    ).status_code == 422
    assert (
        await client.post(_url(event), headers=headers, json=_body(max_per_order=0))
    ).status_code == 422
    window = await client.post(
        _url(event),
        headers=headers,
        json=_body(sales_start_at="2026-12-02T10:00", sales_end_at="2026-12-01T10:00"),
    )
    assert window.status_code == 422
    assert window.json()["error"]["code"] == "invalid_sales_window"


async def test_price_and_quantity_changes_are_audited(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _setup(session)
    tt = await make_ticket_type(session, event, price_kzt=5000, quantity_total=50)
    await session.commit()
    response = await client.patch(
        _url(event, f"/{tt.id}"), headers=headers, json={"price_kzt": 6000, "quantity_total": 80}
    )
    assert response.status_code == 200
    actions = set(
        await session.scalars(
            select(AuditLogEntry.action_type).where(AuditLogEntry.event_id == event.id)
        )
    )
    assert {"ticket_type.price_changed", "ticket_type.quantity_changed"} <= actions


async def test_quantity_cannot_drop_below_sold_and_reserved(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, headers = await _setup(session)
    tt = await make_ticket_type(
        session, event, quantity_total=10, quantity_sold=4, quantity_reserved=2
    )
    await session.commit()
    response = await client.patch(
        _url(event, f"/{tt.id}"), headers=headers, json={"quantity_total": 5}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "quantity_below_sold"
    ok = await client.patch(_url(event, f"/{tt.id}"), headers=headers, json={"quantity_total": 6})
    assert ok.json()["quantity_available"] == 0


async def test_delete_only_if_never_ordered_otherwise_hide(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    organizer = await make_organizer(session)
    event = await make_published_event(session, organizer)
    unused = await make_ticket_type(session, event)
    ordered = await make_ticket_type(session, event)
    buyer = await make_user(session)
    await session.commit()
    headers = await organizer_bearer(session, organizer)
    await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={
            "event_id": str(event.id),
            "items": [{"ticket_type_id": str(ordered.id), "quantity": 1}],
        },
    )

    assert (await client.delete(_url(event, f"/{unused.id}"), headers=headers)).status_code == 204
    blocked = await client.delete(_url(event, f"/{ordered.id}"), headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "ticket_type_has_orders"
    hidden = await client.patch(
        _url(event, f"/{ordered.id}"), headers=headers, json={"is_hidden": True}
    )
    assert hidden.json()["is_hidden"] is True


async def test_other_organizers_cannot_see_or_change_ticket_types(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, event, _ = await _setup(session)
    tt = await make_ticket_type(session, event)
    stranger = await make_organizer(session)
    await session.commit()
    headers = await organizer_bearer(session, stranger)
    assert (await client.get(_url(event), headers=headers)).status_code == 404
    assert (
        await client.patch(_url(event, f"/{tt.id}"), headers=headers, json={"price_kzt": 1})
    ).status_code == 404
