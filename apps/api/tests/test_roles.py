"""Role checks are reusable dependencies (Report 2: Attendee, Organizer, Event Admin,
Platform Admin). Event-scoped checks are tested with the event routes."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import OrganizerUser, PlatformAdminUser
from app.enums import UserRole
from app.main import create_app
from tests.factories import bearer, make_user


@pytest.fixture
async def role_client(db: None) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    @app.get("/_organizer_only")
    async def organizer_only(user: OrganizerUser) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/_admin_only")
    async def admin_only(user: PlatformAdminUser) -> dict[str, str]:
        return {"role": user.role}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.parametrize(
    ("role", "organizer_status", "admin_status"),
    [
        (UserRole.ATTENDEE, 403, 403),
        (UserRole.ORGANIZER, 200, 403),
        # Event admin is a per-event assignment, not a platform role with extra powers.
        (UserRole.EVENT_ADMIN, 403, 403),
        (UserRole.PLATFORM_ADMIN, 403, 200),
    ],
)
async def test_role_dependencies(
    role_client: httpx.AsyncClient,
    session: AsyncSession,
    role: UserRole,
    organizer_status: int,
    admin_status: int,
) -> None:
    user = await make_user(session, role=role)
    await session.commit()
    org = await role_client.get("/_organizer_only", headers=bearer(user))
    admin = await role_client.get("/_admin_only", headers=bearer(user))
    assert org.status_code == organizer_status
    assert admin.status_code == admin_status
    if org.status_code == 403:
        assert org.json()["error"]["code"] == "forbidden"


async def test_role_dependency_requires_sign_in(role_client: httpx.AsyncClient) -> None:
    response = await role_client.get("/_organizer_only")
    assert response.status_code == 401


async def test_suspended_user_token_is_rejected(
    role_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, role=UserRole.ORGANIZER, is_suspended=True)
    await session.commit()
    response = await role_client.get("/_organizer_only", headers=bearer(user))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_suspended"
