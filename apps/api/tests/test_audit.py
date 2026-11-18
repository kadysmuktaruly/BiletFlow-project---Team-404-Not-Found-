"""SRS 4.16: the audit log is append-only. The database trigger rejects UPDATE and DELETE,
whatever the application tries (also covered by tests/constraints/verify_constraints.sql)."""

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLogEntry
from app.services import audit
from tests.factories import make_user


async def test_audit_entries_cannot_be_edited_or_deleted(session: AsyncSession) -> None:
    actor = await make_user(session)
    audit.record(
        session,
        actor_id=actor.id,
        action="order.refunded",
        entity_type="order",
        entity_id=None,
        description="DEMO refund of 8 000 KZT",
    )
    await session.commit()
    entry = await session.scalar(select(AuditLogEntry))
    assert entry is not None
    # Rolling back expires ORM objects; keep plain ids for after.
    entry_id, actor_id = entry.id, actor.id

    with pytest.raises(DBAPIError):
        await session.execute(
            update(AuditLogEntry).where(AuditLogEntry.id == entry_id).values(description="tampered")
        )
    await session.rollback()
    with pytest.raises(DBAPIError):
        await session.execute(delete(AuditLogEntry).where(AuditLogEntry.id == entry_id))
    await session.rollback()

    still = await session.scalar(
        select(AuditLogEntry.description).where(AuditLogEntry.id == entry_id)
    )
    assert still == "DEMO refund of 8 000 KZT"
    # New entries are still accepted.
    audit.record(
        session, actor_id=actor_id, action="x.y", entity_type="x", entity_id=None, description="ok"
    )
    await session.commit()
