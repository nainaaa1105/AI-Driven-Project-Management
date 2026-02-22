"""add_access_type_to_workspace

Revision ID: 297ffd185a97
Revises: 001_multi_user
Create Date: 2026-02-22 10:03:52.586007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '297ffd185a97'
down_revision: Union[str, None] = '001_multi_user'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add access_type with server default so existing rows get the value
    op.add_column('workspaces', sa.Column('access_type', sa.String(length=20), nullable=False, server_default='private'))


def downgrade() -> None:
    op.drop_column('workspaces', 'access_type')
