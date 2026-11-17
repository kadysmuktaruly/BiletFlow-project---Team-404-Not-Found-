"""Report 6 hardening: sign-in, sign-up and account-email endpoints are rate limited per
client IP and per address, without revealing whether an address is registered."""

from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import ratelimit
from app.config import get_settings
from app.main import API_PREFIX
from tests.factories import DEFAULT_PASSWORD, make_user

AUTH = f"{API_PREFIX}/auth"


@pytest.fixture(autouse=True)
def limits_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    ratelimit.reset()
    yield
    ratelimit.reset()


async def test_login_is_limited_per_address_whether_or_not_it_exists(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session)
    await session.commit()
    for email in (user.email, "nobody@example.kz"):
        codes = [
            (
                await client.post(
                    f"{AUTH}/login", json={"email": email, "password": "wrong-pass-1"}
                )
            ).status_code
            for _ in range(6)
        ]
        assert codes == [401] * 5 + [429], email
    blocked = await client.post(
        f"{AUTH}/login", json={"email": user.email, "password": "Password-123"}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    # Another address from the same client still works (the IP limit is higher).
    other = await make_user(session)
    await session.commit()
    ok = await client.post(
        f"{AUTH}/login", json={"email": other.email, "password": DEFAULT_PASSWORD}
    )
    assert ok.status_code == 200, ok.text


async def test_login_is_limited_per_client(client: httpx.AsyncClient) -> None:
    codes = [
        (
            await client.post(
                f"{AUTH}/login", json={"email": f"user{i}@example.kz", "password": "x-password"}
            )
        ).status_code
        for i in range(21)
    ]
    assert codes[:20] == [401] * 20 and codes[20] == 429


async def test_sign_up_and_account_emails_are_limited(client: httpx.AsyncClient) -> None:
    body = {
        "email": "x@example.kz",
        "password": "Password-123",
        "full_name": "X",
        "role": "attendee",
    }
    codes = [
        (
            await client.post(f"{AUTH}/register", json={**body, "email": f"new{i}@example.kz"})
        ).status_code
        for i in range(6)
    ]
    assert codes == [202] * 5 + [429]
    resets = [
        (
            await client.post(f"{AUTH}/forgot-password", json={"email": "someone@example.kz"})
        ).status_code
        for _ in range(4)
    ]
    assert resets == [202] * 3 + [429]


async def test_limits_are_off_for_the_test_suite_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", None)
    assert ratelimit.enabled() is False  # ENVIRONMENT=test
    monkeypatch.setattr(get_settings(), "environment", "development")
    assert ratelimit.enabled() is True
