"""ban system

Revision ID: c550db91be30
Revises: 54a9a6fc599f
Create Date: 2025-05-15 21:55:55.521242

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c550db91be30'
down_revision: Union[str, None] = '54a9a6fc599f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.add_column('server_config', sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='0'))
        op.create_table('banned_member',
                        sa.Column('member_id', sa.Integer(), nullable=False),
                        sa.PrimaryKeyConstraint('member_id')
                        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_column('server_config', 'is_banned')
        op.drop_table('banned_member')
