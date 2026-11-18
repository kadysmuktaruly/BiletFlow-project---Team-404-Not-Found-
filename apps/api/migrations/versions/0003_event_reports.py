"""event reports

SRS 4.12: Platform Admins "review reported events". Signed-in users report an event; an
admin dismisses the report or suspends the event. One open report per person per event.

Revision ID: 0003_event_reports
Revises: 0002_notification_action_path
Create Date: 2026-11-17 16:05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_event_reports"
down_revision: str | Sequence[str] | None = "0002_notification_action_path"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASON = sa.Enum("fraud", "misleading", "inappropriate", "spam", "other", name="event_report_reason")
STATUS = sa.Enum("open", "dismissed", "actioned", name="event_report_status")


def upgrade() -> None:
    op.create_table(
        "event_reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("reporter_user_id", sa.UUID(), nullable=False),
        sa.Column("reason", REASON, nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_event_reports_status_created", "event_reports", ["status", "created_at"], unique=False
    )
    op.create_index(
        "uq_event_reports_open_per_reporter",
        "event_reports",
        ["event_id", "reporter_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("uq_event_reports_open_per_reporter", table_name="event_reports")
    op.drop_index("ix_event_reports_status_created", table_name="event_reports")
    op.drop_table("event_reports")
    STATUS.drop(op.get_bind(), checkfirst=True)
    REASON.drop(op.get_bind(), checkfirst=True)
