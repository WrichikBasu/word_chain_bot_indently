"""used_words_fix

Revision ID: 20d8d765f2f9
Revises: 90213445d026
Create Date: 2025-06-23 17:50:16.678788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20d8d765f2f9'
down_revision: Union[str, None] = '90213445d026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        with op.batch_alter_table('used_words', schema=None) as batch_op:
            batch_op.add_column(sa.Column('game_mode', sa.Integer(), nullable=True))

        op.execute('UPDATE used_words SET game_mode = 1')

        with op.batch_alter_table('used_words', schema=None) as batch_op:
            batch_op.alter_column('game_mode', nullable=False)
            batch_op.create_primary_key('primary_key', ['server_id', 'game_mode', 'word'])


def downgrade() -> None:
    op.drop_column('used_words', 'game_mode')
