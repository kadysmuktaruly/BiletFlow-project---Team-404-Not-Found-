"""notification action path

In-app notifications (SRS 4.10, 4.13) need to lead somewhere in the web app. Support cases
have no column on `notifications` to derive a link from, so store the web path itself.
Nullable, no default, no backfill: existing rows simply have no link.

Revision ID: 0002_notification_action_path
Revises: 0001_initial
Create Date: 2026-11-17 15:18:11.186211

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_notification_action_path'
down_revision: Union[str, Sequence[str], None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('notifications', sa.Column('action_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('notifications', 'action_path')
