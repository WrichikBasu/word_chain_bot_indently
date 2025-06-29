"""hard-mode

Revision ID: 90213445d026
Revises: c550db91be30
Create Date: 2025-06-10 22:08:42.663113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90213445d026'
down_revision: Union[str, None] = 'c550db91be30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        with op.batch_alter_table('server_config', schema=None) as batch_op:
            batch_op.add_column(sa.Column('hard_mode_channel_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('hard_mode_last_member_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('hard_mode_current_count', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('hard_mode_current_word', sa.String(), nullable=True))
            batch_op.add_column(sa.Column('hard_mode_high_score', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('hard_mode_used_high_score_emoji', sa.Boolean(), nullable=True))

        op.execute('UPDATE server_config SET hard_mode_current_count = 0')
        op.execute('UPDATE server_config SET hard_mode_high_score = 0')
        op.execute('UPDATE server_config SET hard_mode_used_high_score_emoji = 0')

        with op.batch_alter_table('server_config', schema=None) as batch_op:
            batch_op.alter_column('hard_mode_current_count', nullable=False)
            batch_op.alter_column('hard_mode_high_score', nullable=False)
            batch_op.alter_column('hard_mode_used_high_score_emoji', nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('server_config', schema=None) as batch_op:
        batch_op.drop_column('hard_mode_used_high_score_emoji')
        batch_op.drop_column('hard_mode_high_score')
        batch_op.drop_column('hard_mode_current_word')
        batch_op.drop_column('hard_mode_current_count')
        batch_op.drop_column('hard_mode_last_member_id')
        batch_op.drop_column('hard_mode_channel_id')
