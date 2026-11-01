"""Test harness: a throwaway `<name>_test` database, migrated once per run.

How it fits together:

* `DATABASE_URL` is rewritten to point at `<name>_test` **before** any `app` module is
  imported, because `app.db` builds its engine at import time. The dev database is never
  touched; `_test_database_url` refuses to run against a name without the suffix.
* The test database is dropped and recreated at the start of every run, then migrated with
  Alembic, so the schema under test is exactly what the migrations produce.
* Tests that need the database request the `db` fixture (or `client`, which depends on it).
  It truncates every table first. TRUNCATE skips row-level triggers, which is why the
  append-only audit trigger does not get in the way.
* Every test shares one event loop (see `asyncio_default_*_loop_scope` in pyproject.toml).
  asyncpg connections belong to the loop that opened them, and the app's engine is a
  module-level singleton, so a fresh loop per test would hand out dead pooled connections.
* Concurrency tests are real: requests sent with `asyncio.gather` through the client each
  check out their own pooled connection, so Postgres sees genuinely concurrent transactions.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

_API_DIR = Path(__file__).resolve().parent.parent


def _test_database_url() -> str:
    # Read the configured URL the same way the app does (env var, then .env files).
    from app.config import Settings

    url = make_url(Settings().database_url)
    name = url.database or "biletflow"
    if not name.endswith("_test"):
        name = f"{name}_test"
    return url.set(database=name).render_as_string(hide_password=False)


os.environ["DATABASE_URL"] = _test_database_url()
os.environ["ENVIRONMENT"] = "test"
os.environ["EMAIL_BACKEND"] = "memory"

# Only now is it safe to import anything that touches the engine.
import asyncpg  # noqa: E402
import httpx  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.mail import OutgoingEmail, outbox  # noqa: E402

get_settings.cache_clear()
assert get_settings().database_url.rsplit("/", 1)[-1].endswith("_test")


def _plain_dsn(sqlalchemy_url: str) -> str:
    """asyncpg wants `postgresql://`, not SQLAlchemy's `postgresql+asyncpg://`."""
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _recreate_test_database() -> None:
    url = make_url(get_settings().database_url)
    test_db = url.database
    assert test_db is not None and test_db.endswith("_test")
    admin = await asyncpg.connect(_plain_dsn(url.set(database="postgres").render_as_string(False)))
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{test_db}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{test_db}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_database() -> Iterator[None]:
    """Fresh database, migrated to head. Synchronous on purpose: Alembic's env.py calls
    `asyncio.run`, which cannot run inside the test event loop."""
    asyncio.run(_recreate_test_database())
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "migrations"))
    command.upgrade(cfg, "head")
    yield


_TABLES = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)


@pytest.fixture
async def db() -> AsyncIterator[None]:
    """Empty tables. Request this (or `client`) in any test that touches the database."""
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
    outbox().clear()
    yield


@pytest.fixture
def mail(db: None) -> list[OutgoingEmail]:
    """Emails the app has "sent" during this test (EMAIL_BACKEND=memory), oldest first."""
    return outbox()


@pytest.fixture
async def session(db: None) -> AsyncIterator[AsyncSession]:
    """A session for arranging and inspecting data directly. Commit what you arrange."""
    async with SessionLocal() as s:
        yield s


@pytest.fixture
async def client(db: None) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def raw_dsn() -> str:
    """Plain asyncpg DSN for the test database, for tests that need raw SQL features."""
    return _plain_dsn(get_settings().database_url)
