"""sql native types

Revision ID: 0a25d147de45
Revises: 8aa564d9e627
Create Date: 2024-10-17 19:56:30.198874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a25d147de45'
down_revision: Union[str, None] = '8aa564d9e627'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('blacklist', schema=None) as batch_op:
        batch_op.alter_column('word',
                               existing_type=sa.TEXT(),
                               type_=sa.String(),
                               existing_nullable=False)

    with op.batch_alter_table('whitelist', schema=None) as batch_op:
        batch_op.alter_column('word',
                               existing_type=sa.TEXT(),
                               type_=sa.String(),
                               existing_nullable=False)

    with op.batch_alter_table('member', schema=None) as batch_op:
        batch_op.alter_column('karma',
                               existing_type=sa.REAL(),
                               type_=sa.Float(),
                               existing_nullable=False)

    with op.batch_alter_table('used_words', schema=None) as batch_op:
        batch_op.alter_column('word',
                               existing_type=sa.TEXT(),
                               type_=sa.String(),
                               existing_nullable=False)

    with op.batch_alter_table('word_cache', schema=None) as batch_op:
        batch_op.alter_column('word',
                               existing_type=sa.TEXT(),
                               type_=sa.String(),
                               nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('blacklist', schema=None) as batch_op:
        batch_op.alter_column('word',
                              existing_type=sa.String(),
                              type_=sa.TEXT(),
                              existing_nullable=True)

    with op.batch_alter_table('whitelist', schema=None) as batch_op:
        batch_op.alter_column('word',
                              existing_type=sa.String(),
                              type_=sa.TEXT(),
                              existing_nullable=True)

    with op.batch_alter_table('member', schema=None) as batch_op:
        batch_op.alter_column('karma',
                              existing_type=sa.Float(),
                              type_=sa.REAL(),
                              existing_nullable=True)

    with op.batch_alter_table('used_words', schema=None) as batch_op:
        batch_op.alter_column('word',
                              existing_type=sa.String(),
                              type_=sa.TEXT(),
                              existing_nullable=True)

    with op.batch_alter_table('word_cache', schema=None) as batch_op:
        batch_op.alter_column('word',
                              existing_type=sa.String(),
                              type_=sa.TEXT(),
                              nullable=True)
