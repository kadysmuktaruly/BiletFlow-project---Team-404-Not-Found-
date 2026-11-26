"""user deleted_at

Users can delete their own account. The row can't be removed, because orders, tickets,
refunds, campaigns and support cases reference it with ON DELETE RESTRICT and the audit
trail (SRS 4.16) must keep its history. Instead the row is scrubbed of personal data and
stamped with `deleted_at`, which also stops every token issued before the deletion.
Nullable, no default, no backfill: no existing account is deleted.

Revision ID: 0005_user_deleted_at
Revises: 0004_platform_settings
Create Date: 2026-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_user_deleted_at'
down_revision: Union[str, Sequence[str], None] = '0004_platform_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'deleted_at')
