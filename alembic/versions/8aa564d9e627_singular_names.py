"""singular names

Revision ID: 8aa564d9e627
Revises: d060a8ef2794
Create Date: 2024-10-17 19:48:30.293364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8aa564d9e627'
down_revision: Union[str, None] = 'd060a8ef2794'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('blacklist',  schema=None) as batch_op:
        batch_op.alter_column('words', new_column_name='word')

    with op.batch_alter_table('whitelist',  schema=None) as batch_op:
        batch_op.alter_column('words', new_column_name='word')

    with op.batch_alter_table('used_words',  schema=None) as batch_op:
        batch_op.alter_column('words', new_column_name='word')

    with op.batch_alter_table('word_cache',  schema=None) as batch_op:
        batch_op.alter_column('words', new_column_name='word')

    op.rename_table('members', 'member')


def downgrade() -> None:
    with op.batch_alter_table('blacklist',  schema=None) as batch_op:
        batch_op.alter_column('word', new_column_name='words')

    with op.batch_alter_table('whitelist',  schema=None) as batch_op:
        batch_op.alter_column('word', new_column_name='words')

    with op.batch_alter_table('used_words',  schema=None) as batch_op:
        batch_op.alter_column('word', new_column_name='words')

    with op.batch_alter_table('word_cache',  schema=None) as batch_op:
        batch_op.alter_column('word', new_column_name='words')

    op.rename_table('member', 'members')
