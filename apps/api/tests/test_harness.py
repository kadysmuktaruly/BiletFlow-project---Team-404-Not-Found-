"""The DB-backed harness itself: real database, real migrations, clean tables per test."""

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import API_PREFIX
from app.models import User
from tests.factories import make_user


async def test_health_against_real_test_database(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_rows_written_by_one_test(session: AsyncSession) -> None:
    await make_user(session, email="first@example.com")
    await session.commit()
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_are_gone_in_the_next(session: AsyncSession) -> None:
    assert await session.scalar(select(func.count()).select_from(User)) == 0
