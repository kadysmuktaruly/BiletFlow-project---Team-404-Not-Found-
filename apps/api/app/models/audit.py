"""Audit Log (SRS 4.16).

SRS 4.16: "Audit entries shall not be editable or deletable through normal organizer
interfaces." This module makes that structural rather than conventional:

* No `updated_at` and no TimestampMixin — an audit row has one time, the time it
  happened, and a column that changes is a column someone will change.
* No relationship anywhere in the codebase cascade-deletes into this table.
* A BEFORE UPDATE OR DELETE trigger, installed by the initial migration, raises on any
  attempt. See `migrations/versions/0001_initial.py`.

The trigger is deliberately chosen over `REVOKE UPDATE, DELETE`: a grant applies to one
role, and the team connects as the owner in development, where the mistake is most likely
to be made. A trigger holds for every role including the table owner.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class AuditLogEntry(Base):
    """SRS 4.16: "a timestamp, acting user, action type, affected entity, and short
    description" — those five fields, plus the entity id needed to actually navigate to
    the thing that changed.

    `action_type` and `entity_type` are **strings, not enums**, and that is a considered
    choice. Every other status column in this schema is a native Postgres enum. Here, a
    native enum would mean an `ALTER TYPE ... ADD VALUE` migration every time anyone logs
    a new kind of action — and SRS 4.16 lists nine categories that will keep growing
    weekly across Weeks 3-9, touched by all five people. The convention is a dotted
    lowercase pair, `entity.verb`: `event.published`, `ticket.checked_in`,
    `promo_code.disabled`, `refund.completed`.
    """

    __tablename__ = "audit_log_entries"

    id: Mapped[uuid.UUID] = uuid_pk()

    occurred_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )
    # NULL only for platform-initiated actions (an expiry sweep has no acting user).
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Denormalised so the organizer timeline (SRS 4.16) can be filtered by event without
    # joining through six different entity types to find out which event a row belongs to.
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )

    __table_args__ = (
        # SRS 4.16: "filter history by date range and activity type", scoped to one event.
        Index("ix_audit_event_occurred", "event_id", "occurred_at"),
        Index("ix_audit_action_type", "action_type"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )
