"""rename high score emoji flag

Revision ID: b9bee291a668
Revises: 364e8b6e33f8
Create Date: 2024-10-21 20:20:55.070911

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9bee291a668'
down_revision: Union[str, None] = '364e8b6e33f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('server_config', schema=None) as batch_op:
        batch_op.alter_column('put_high_score_emoji', new_column_name='used_high_score_emoji')


def downgrade() -> None:
    with op.batch_alter_table('server_config', schema=None) as batch_op:
        batch_op.alter_column('used_high_score_emoji', new_column_name='put_high_score_emoji')
