"""Runs tests/constraints/verify_constraints.sql against the migrated test database.

The script is the source of truth for the database-enforced guarantees (see its README).
Running it from pytest means CI checks them on every pull request. It prints one
`PASS ...` notice per guarantee, or a `FAIL ...` warning if Postgres accepted something it
should have refused.
"""

import asyncio
from pathlib import Path

import asyncpg
import pytest

_SCRIPT = Path(__file__).parent / "constraints" / "verify_constraints.sql"


@pytest.mark.usefixtures("db")
async def test_database_constraints_hold(raw_dsn: str) -> None:
    # psql meta-commands (`\set ...`) are not SQL; asyncpg would reject them.
    sql = "\n".join(line for line in _SCRIPT.read_text().splitlines() if not line.startswith("\\"))
    messages: list[str] = []
    conn = await asyncpg.connect(raw_dsn)
    conn.add_log_listener(lambda _conn, msg: messages.append(msg.message))
    try:
        await conn.execute(sql)
        # Log listeners are invoked via the event loop; let them run before closing.
        await asyncio.sleep(0)
    finally:
        await conn.close()

    failures = [m for m in messages if m.startswith("FAIL")]
    passes = [m for m in messages if m.startswith("PASS")]
    assert not failures, failures
    # One PASS per `expect_failure(...)` call, plus one per must-succeed `DO` block. The
    # helper function's own `RAISE NOTICE 'PASS` line is a template, not a check.
    script = _SCRIPT.read_text()
    expected = script.count("SELECT expect_failure(") + script.count("RAISE NOTICE 'PASS") - 1
    assert len(passes) == expected, passes
