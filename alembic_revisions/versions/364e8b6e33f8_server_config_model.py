"""server config model

Revision ID: 364e8b6e33f8
Revises: 0a25d147de45
Create Date: 2024-10-18 09:40:52.529806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '364e8b6e33f8'
down_revision: Union[str, None] = '0a25d147de45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('server_config',
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('channel_id', sa.Integer(), nullable=True),
    sa.Column('current_count', sa.Integer(), nullable=False),
    sa.Column('current_word', sa.String(), nullable=True),
    sa.Column('high_score', sa.Integer(), nullable=False),
    sa.Column('put_high_score_emoji', sa.Boolean(), nullable=False),
    sa.Column('reliable_role_id', sa.Integer(), nullable=True),
    sa.Column('failed_role_id', sa.Integer(), nullable=True),
    sa.Column('last_member_id', sa.Integer(), nullable=True),
    sa.Column('failed_member_id', sa.Integer(), nullable=True),
    sa.Column('correct_inputs_by_failed_member', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('server_id')
    )


def downgrade() -> None:
    op.drop_table('server_config')
