"""Deleting your own account (DELETE /me).

Not an SRS 4.1 requirement; see `app.services.account` for why the row is anonymised
rather than removed.
"""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, NotificationChannel, NotificationType, UserRole
from app.main import API_PREFIX
from app.models import (
    AuditLogEntry,
    Notification,
    Order,
    OrganizerProfile,
    StaffAssignment,
    User,
)
from app.services.auth import issue_tokens
from tests.factories import (
    DEFAULT_PASSWORD,
    bearer,
    make_event,
    make_organizer,
    make_published_event,
    make_ticket_type,
    make_user,
)

ME = f"{API_PREFIX}/me"
AUTH = f"{API_PREFIX}/auth"


async def _delete(
    client: httpx.AsyncClient, headers: dict[str, str], password: str = DEFAULT_PASSWORD
) -> httpx.Response:
    return await client.request("DELETE", ME, headers=headers, json={"password": password})


async def test_delete_anonymises_the_account_and_ends_every_session(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, email="Leaving@Example.com", phone="+77010000000")
    session.add(
        Notification(
            user_id=user.id,
            type=NotificationType.ACCOUNT_VERIFICATION,
            channel=NotificationChannel.IN_APP,
            subject="Hi",
            body="Hello",
        )
    )
    await session.commit()
    headers = bearer(user)
    _, refresh = issue_tokens(user)

    response = await _delete(client, headers)
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "bf_refresh=" in cookie and "Path=/api/v1/auth" in cookie

    await session.refresh(user)
    assert user.deleted_at is not None
    assert user.email == f"deleted-{user.id}@deleted.invalid"
    assert user.full_name == "Deleted account"
    assert user.phone is None
    count = select(func.count(Notification.id)).where(Notification.user_id == user.id)
    assert await session.scalar(count) == 0

    entry = await session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action_type == "user.account_deleted")
    )
    assert entry is not None and entry.actor_user_id == user.id
    assert "leaving" not in entry.description.lower()

    # The old access token, refresh token and password all stop working.
    assert (await client.get(ME, headers=headers)).status_code == 401
    assert (
        await client.post(f"{AUTH}/refresh", json={"refresh_token": refresh})
    ).status_code == 401
    login = await client.post(
        f"{AUTH}/login", json={"email": "leaving@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 401
    assert login.json()["error"]["code"] == "invalid_credentials"


async def test_the_email_can_register_again_after_deletion(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, email="again@example.com")
    await session.commit()
    assert (await _delete(client, bearer(user))).status_code == 204

    response = await client.post(
        f"{AUTH}/register",
        json={"email": "again@example.com", "password": "s3cret-pass", "full_name": "New"},
    )
    assert response.status_code == 202
    fresh = await session.scalar(select(User).where(User.email == "again@example.com"))
    assert fresh is not None and fresh.id != user.id and fresh.deleted_at is None


async def test_wrong_password_deletes_nothing(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, email="stay@example.com")
    await session.commit()

    response = await _delete(client, bearer(user), password="not-my-password")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_password"
    await session.refresh(user)
    assert user.deleted_at is None and user.email == "stay@example.com"
    assert (await client.get(ME, headers=bearer(user))).status_code == 200


async def test_delete_requires_sign_in_and_a_password(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    assert (
        await client.request("DELETE", ME, json={"password": DEFAULT_PASSWORD})
    ).status_code == 401
    user = await make_user(session)
    await session.commit()
    missing = await client.request("DELETE", ME, headers=bearer(user), json={})
    assert missing.status_code == 422


async def test_buyer_with_orders_can_delete_and_orders_are_kept(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    event = await make_published_event(session)
    free = await make_ticket_type(session, event, price_kzt=0)
    buyer = await make_user(session)
    await session.commit()
    order = await client.post(
        f"{API_PREFIX}/orders",
        headers=bearer(buyer),
        json={
            "event_id": str(event.id),
            "items": [{"ticket_type_id": str(free.id), "quantity": 1}],
            "attendees": [{"full_name": "A N"}],
        },
    )
    assert order.status_code == 201

    assert (await _delete(client, bearer(buyer))).status_code == 204
    orders = select(func.count(Order.id)).where(Order.user_id == buyer.id)
    assert await session.scalar(orders) == 1


async def test_platform_admin_cannot_delete_their_account(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    admin = await make_user(session, role=UserRole.PLATFORM_ADMIN)
    await session.commit()
    response = await _delete(client, bearer(admin))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_delete_admin"


async def test_organizer_with_a_live_event_must_cancel_it_first(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    profile = await make_organizer(session)
    event = await make_published_event(session, profile)
    user = await session.get_one(User, profile.user_id)
    await session.commit()

    response = await _delete(client, bearer(user))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "organizer_has_live_events"

    event.status = EventStatus.CANCELLED
    await session.commit()
    assert (await _delete(client, bearer(user))).status_code == 204


async def test_organizer_with_past_events_can_delete_and_contact_details_are_cleared(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    profile = await make_organizer(session, full_name="Organizer Org")
    profile.contact_phone = "+77010000000"
    profile.website_url = "https://example.com"
    past = datetime.now(UTC) - timedelta(days=10)
    await make_event(session, profile, status=EventStatus.PUBLISHED, starts_at=past, ends_at=past)
    await make_event(session, profile)  # a draft
    user = await session.get_one(User, profile.user_id)
    await session.commit()

    assert (await _delete(client, bearer(user))).status_code == 204
    await session.refresh(profile)
    assert profile.contact_email == f"deleted-{user.id}@deleted.invalid"
    assert profile.contact_phone is None and profile.website_url is None
    # The public name printed on past events and tickets stays.
    assert profile.display_name == "Organizer Org"


async def test_deleting_revokes_staff_assignments(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    profile = await make_organizer(session)
    event = await make_published_event(session, profile)
    staff = await make_user(session)
    session.add(
        StaffAssignment(event_id=event.id, user_id=staff.id, assigned_by_user_id=profile.user_id)
    )
    await session.commit()

    assert (await _delete(client, bearer(staff))).status_code == 204
    assignment = await session.scalar(
        select(StaffAssignment).where(StaffAssignment.user_id == staff.id)
    )
    assert assignment is not None and assignment.revoked_at is not None
    assert (
        await session.scalar(
            select(OrganizerProfile.id).where(OrganizerProfile.user_id == staff.id)
        )
        is None
    )
