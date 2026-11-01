"""SRS 4.1: register, verify, sign in and out, refresh, reset password."""

import re
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NotificationStatus, NotificationType, UserRole
from app.main import API_PREFIX
from app.models import Notification, OrganizerProfile, User
from app.security import TokenType, create_token
from app.services.mail import OutgoingEmail
from tests.factories import DEFAULT_PASSWORD, bearer, make_user

AUTH = f"{API_PREFIX}/auth"


def _token_from(msg: OutgoingEmail) -> str:
    url = re.search(r"https?://\S+token=\S+", msg.text)
    assert url, msg.text
    return parse_qs(urlparse(url.group(0)).query)["token"][0]


async def _register(client: httpx.AsyncClient, **overrides: str) -> httpx.Response:
    body = {
        "email": "aigerim@example.com",
        "password": "s3cret-pass",
        "full_name": "Aigerim N",
        **overrides,
    }
    return await client.post(f"{AUTH}/register", json=body)


# --- registration -------------------------------------------------------------------


async def test_register_creates_unverified_attendee_and_sends_verification(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    response = await _register(client, locale="en")
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}

    user = (await session.execute(select(User))).scalar_one()
    assert user.role is UserRole.ATTENDEE
    assert not user.is_email_verified
    assert user.hashed_password.startswith("$argon2")

    assert len(mail) == 1
    assert mail[0].to == "aigerim@example.com"
    assert mail[0].template == "verify_email"
    assert "/en/verify-email?token=" in mail[0].text

    notification = (await session.execute(select(Notification))).scalar_one()
    assert notification.type is NotificationType.ACCOUNT_VERIFICATION
    assert notification.status is NotificationStatus.SENT


async def test_verification_email_uses_the_users_language(
    client: httpx.AsyncClient, mail: list[OutgoingEmail]
) -> None:
    await _register(client, locale="ru")
    assert mail[0].subject == "Подтвердите адрес электронной почты в BiletFlow"
    assert "/ru/verify-email" in mail[0].text


async def test_register_as_organizer_creates_profile(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await _register(client, role="organizer")
    user = (await session.execute(select(User))).scalar_one()
    assert user.role is UserRole.ORGANIZER
    profile = (await session.execute(select(OrganizerProfile))).scalar_one()
    assert profile.user_id == user.id
    assert profile.contact_email == user.email


@pytest.mark.parametrize("role", ["platform_admin", "event_admin"])
async def test_register_cannot_self_assign_privileged_roles(
    client: httpx.AsyncClient, session: AsyncSession, role: str
) -> None:
    response = await _register(client, role=role)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert await session.scalar(select(func.count()).select_from(User)) == 0


async def test_register_existing_email_looks_identical_and_sends_nothing(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    await make_user(session, email="taken@example.com")
    await session.commit()

    response = await _register(client, email="TAKEN@example.com")
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert mail == []
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_register_rejects_short_password(client: httpx.AsyncClient) -> None:
    response = await _register(client, password="short")
    assert response.status_code == 422


# --- email verification ---------------------------------------------------------------


async def test_verify_email_with_emailed_token(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    await _register(client)
    response = await client.post(f"{AUTH}/verify-email", json={"token": _token_from(mail[0])})
    assert response.status_code == 200
    assert response.json()["is_email_verified"] is True

    user = (await session.execute(select(User))).scalar_one()
    await session.refresh(user)
    assert user.is_email_verified
    assert user.email_verified_at is not None


async def test_verify_email_rejects_a_token_minted_for_another_purpose(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, is_email_verified=False)
    await session.commit()
    access = create_token(TokenType.ACCESS, user.id)
    response = await client.post(f"{AUTH}/verify-email", json={"token": access})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_token"


async def test_resend_verification_never_reveals_whether_email_exists(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    await make_user(session, email="pending@example.com", is_email_verified=False)
    await session.commit()

    known = await client.post(f"{AUTH}/resend-verification", json={"email": "pending@example.com"})
    unknown = await client.post(f"{AUTH}/resend-verification", json={"email": "nobody@example.com"})
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    assert [m.to for m in mail] == ["pending@example.com"]


# --- sign in, refresh, sign out --------------------------------------------------------


async def test_login_sets_httponly_refresh_cookie_for_browsers(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, email="web@example.com")
    await session.commit()

    response = await client.post(
        f"{AUTH}/login", json={"email": "WEB@example.com", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == str(user.id)
    assert body["refresh_token"] is None
    cookie = response.headers["set-cookie"]
    assert "bf_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth" in cookie

    me = await client.get(
        f"{API_PREFIX}/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.json()["email"] == "web@example.com"


async def test_login_returns_refresh_token_in_body_for_scanner(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="staff@example.com")
    await session.commit()
    response = await client.post(
        f"{AUTH}/login",
        json={"email": "staff@example.com", "password": DEFAULT_PASSWORD},
        headers={"X-Client": "scanner"},
    )
    assert response.json()["refresh_token"]
    assert "set-cookie" not in response.headers


async def test_login_errors_do_not_reveal_whether_email_exists(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="real@example.com")
    await session.commit()
    wrong_password = await client.post(
        f"{AUTH}/login", json={"email": "real@example.com", "password": "wrong-password"}
    )
    unknown_email = await client.post(
        f"{AUTH}/login", json={"email": "ghost@example.com", "password": "wrong-password"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"


async def test_suspended_user_cannot_sign_in(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="banned@example.com", is_suspended=True)
    await session.commit()
    response = await client.post(
        f"{AUTH}/login", json={"email": "banned@example.com", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_suspended"


async def test_refresh_with_cookie_and_with_body(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="r@example.com")
    await session.commit()
    creds = {"email": "r@example.com", "password": DEFAULT_PASSWORD}

    await client.post(f"{AUTH}/login", json=creds)  # cookie stored by the client
    via_cookie = await client.post(f"{AUTH}/refresh")
    assert via_cookie.status_code == 200
    assert via_cookie.json()["access_token"]

    scanner = await client.post(f"{AUTH}/login", json=creds, headers={"X-Client": "scanner"})
    client.cookies.clear()
    via_body = await client.post(
        f"{AUTH}/refresh",
        json={"refresh_token": scanner.json()["refresh_token"]},
        headers={"X-Client": "scanner"},
    )
    assert via_body.status_code == 200
    assert via_body.json()["refresh_token"]


async def test_refresh_rejects_access_tokens_and_garbage(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session)
    await session.commit()
    access = create_token(TokenType.ACCESS, user.id)
    for token in (access, "not-a-jwt"):
        response = await client.post(f"{AUTH}/refresh", json={"refresh_token": token})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
    assert (await client.post(f"{AUTH}/refresh")).status_code == 401


async def test_logout_clears_cookie(client: httpx.AsyncClient) -> None:
    response = await client.post(f"{AUTH}/logout")
    assert response.status_code == 204
    assert 'bf_refresh=""' in response.headers["set-cookie"]


# --- password reset ---------------------------------------------------------------------


async def test_forgot_password_never_reveals_whether_email_exists(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    await make_user(session, email="known@example.com")
    await session.commit()
    known = await client.post(f"{AUTH}/forgot-password", json={"email": "known@example.com"})
    unknown = await client.post(f"{AUTH}/forgot-password", json={"email": "who@example.com"})
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    assert [m.template for m in mail] == ["reset_password"]


async def test_reset_password_is_single_use_and_ends_other_sessions(
    client: httpx.AsyncClient, session: AsyncSession, mail: list[OutgoingEmail]
) -> None:
    await make_user(session, email="forgetful@example.com")
    await session.commit()
    old_session = await client.post(
        f"{AUTH}/login",
        json={"email": "forgetful@example.com", "password": DEFAULT_PASSWORD},
        headers={"X-Client": "scanner"},
    )
    await client.post(f"{AUTH}/forgot-password", json={"email": "forgetful@example.com"})
    token = _token_from(mail[0])

    first = await client.post(
        f"{AUTH}/reset-password", json={"token": token, "new_password": "brand-new-pass"}
    )
    assert first.status_code == 204
    again = await client.post(
        f"{AUTH}/reset-password", json={"token": token, "new_password": "another-pass"}
    )
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_token"

    stale = await client.post(
        f"{AUTH}/refresh", json={"refresh_token": old_session.json()["refresh_token"]}
    )
    assert stale.status_code == 401

    new_login = await client.post(
        f"{AUTH}/login", json={"email": "forgetful@example.com", "password": "brand-new-pass"}
    )
    assert new_login.status_code == 200


# --- /me --------------------------------------------------------------------------------


async def test_me_requires_a_valid_access_token(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"

    bad = await client.get(f"{API_PREFIX}/me", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


async def test_me_update_cannot_change_role_or_email(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, email="me@example.com")
    await session.commit()
    response = await client.patch(
        f"{API_PREFIX}/me",
        json={"locale": "en", "full_name": "New Name", "role": "platform_admin", "email": "x@x.kz"},
        headers=bearer(user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "en"
    assert body["full_name"] == "New Name"
    assert body["role"] == "attendee"
    assert body["email"] == "me@example.com"
