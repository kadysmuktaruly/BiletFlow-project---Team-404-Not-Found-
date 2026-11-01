"""Append-only audit trail (SRS 4.16). The database trigger forbids edits and deletes."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLogEntry


def record(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    description: str,
    event_id: uuid.UUID | None = None,
) -> None:
    """Add an entry to the current transaction. `action` is `entity.verb`, e.g.
    `event.published`, `ticket.checked_in`, `ticket_type.price_changed`."""
    session.add(
        AuditLogEntry(
            actor_user_id=actor_id,
            action_type=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            event_id=event_id,
        )
    )
