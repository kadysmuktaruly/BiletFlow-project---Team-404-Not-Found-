"""platform settings

SRS 4.12: Platform Admins "configure activation fees and platform settings". One row at
most (`singleton`); with no row, the API uses ACTIVATION_FEE_KZT from the environment, so
existing deployments behave exactly as before until an admin changes the fee.

Revision ID: 0004_platform_settings
Revises: 0003_event_reports
Create Date: 2026-11-17 16:06:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_platform_settings"
down_revision: str | Sequence[str] | None = "0003_event_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("singleton", sa.Boolean(), nullable=False),
        sa.Column("activation_fee_kzt", sa.BigInteger(), nullable=False),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "activation_fee_kzt >= 0", name="ck_platform_settings_activation_fee_non_negative"
        ),
        sa.CheckConstraint("singleton", name="ck_platform_settings_singleton"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton", name="uq_platform_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
