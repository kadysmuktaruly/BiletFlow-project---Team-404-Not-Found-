"""Platform administration (SRS 4.12): reported events and runtime platform settings.

Both were added in Report 5 (migrations 0003 and 0004), not in the initial schema:
* SRS 4.12 requires admins to "review reported events", which needs a place to store reports.
* SRS 4.12 requires admins to "configure activation fees", which needs a value the API reads
  at runtime instead of only `ACTIVATION_FEE_KZT` from the environment.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import EventReportReason, EventReportStatus
from app.models.base import Base, TimestampMixin, pg_enum, uuid_pk


class EventReport(Base, TimestampMixin):
    """A signed-in user reports an event; a Platform Admin reviews it."""

    __tablename__ = "event_reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[EventReportReason] = mapped_column(
        pg_enum(EventReportReason, "event_report_reason"), nullable=False
    )
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EventReportStatus] = mapped_column(
        pg_enum(EventReportStatus, "event_report_status"),
        nullable=False,
        default=EventReportStatus.OPEN,
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column()
    review_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # One open report per person per event: reporting again doesn't pile up duplicates.
        Index(
            "uq_event_reports_open_per_reporter",
            "event_id",
            "reporter_user_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_event_reports_status_created", "status", "created_at"),
    )


class PlatformSettings(Base, TimestampMixin):
    """Settings a Platform Admin changes at runtime. Exactly one row (or none: then the
    environment defaults apply, e.g. `ACTIVATION_FEE_KZT`)."""

    __tablename__ = "platform_settings"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Always true; unique, so a second row can't be inserted.
    singleton: Mapped[bool] = mapped_column(nullable=False, default=True)
    # Whole KZT. Applies to activation fees paid from now on; fees already paid keep their
    # recorded amount (PaidSalesActivation.activation_fee_kzt).
    activation_fee_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("singleton", name="uq_platform_settings_singleton"),
        CheckConstraint("singleton", name="ck_platform_settings_singleton"),
        CheckConstraint(
            "activation_fee_kzt >= 0", name="ck_platform_settings_activation_fee_non_negative"
        ),
    )
