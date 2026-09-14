"""Support Case and Support Message (SRS 4.13).

SRS 4.13 scopes the MVP tightly: asynchronous, REST-with-polling. No typing indicators,
no presence, no WebSockets, no AI chatbot. These two tables are all that requires.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import SupportCaseStatus, SupportCategory
from app.models.base import Base, TimestampMixin, pg_enum, uuid_pk


class SupportCase(Base, TimestampMixin):
    """SRS 4.13.

    The three nullable context FKs are the "automatically include the relevant user,
    event, order, and ticket context when available" requirement. They are also the
    authorization surface: SRS 7 requires access be enforced "by role **and by
    relationship** to the relevant event, order, or ticket", so a Week 8 permission check
    reads these columns rather than a role alone.
    """

    __tablename__ = "support_cases"

    id: Mapped[uuid.UUID] = uuid_pk()
    reference: Mapped[str] = mapped_column(String(32), nullable=False)

    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[SupportCategory] = mapped_column(
        pg_enum(SupportCategory, "support_category"), nullable=False
    )
    status: Mapped[SupportCaseStatus] = mapped_column(
        pg_enum(SupportCaseStatus, "support_case_status"),
        nullable=False,
        default=SupportCaseStatus.OPEN,
    )
    subject: Mapped[str] = mapped_column(String(300), nullable=False)

    # SRS 4.13 distinguishes attendee cases (attendee <-> organizer staff) from organizer
    # cases (organizer <-> Platform Admin). The two have different participants, so the
    # distinction has to be stored, not inferred from who opened the case.
    is_organizer_case: Mapped[bool] = mapped_column(nullable=False, default=False)

    event_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL")
    )

    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime | None] = mapped_column()
    resolved_at: Mapped[datetime | None] = mapped_column()
    last_message_at: Mapped[datetime | None] = mapped_column()

    messages: Mapped[list[SupportMessage]] = relationship(back_populates="case")

    __table_args__ = (
        UniqueConstraint("reference", name="uq_support_cases_reference"),
        Index("ix_support_cases_opened_by", "opened_by_user_id", "created_at"),
        Index("ix_support_cases_event_status", "event_id", "status"),
        Index("ix_support_cases_assigned", "assigned_to_user_id", "status"),
    )


class SupportMessage(Base, TimestampMixin):
    """One message in a case thread (SRS 4.13).

    `is_internal_note` lets staff annotate a case without the requester seeing it. The
    Read schema for a requester must filter these out — see app/schemas/support.py.
    """

    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("support_cases.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal_note: Mapped[bool] = mapped_column(nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column()

    case: Mapped[SupportCase] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_support_messages_case_created", "case_id", "created_at"),)
