"""serbian to serbo-croatian

Revision ID: c62c307d3191
Revises: 3c0da61070c4
Create Date: 2025-12-05 10:23:55.325882

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c62c307d3191'
down_revision: Union[str, None] = '3c0da61070c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE server_config SET languages = replace(languages, 'sr', 'sh')")
    op.execute("UPDATE word_cache SET language = 'sh' WHERE language = 'sr'")


def downgrade() -> None:
    op.execute("UPDATE server_config SET languages = replace(languages, 'sh', 'sr')")
    op.execute("UPDATE word_cache SET language = 'sr' WHERE language = 'sh'")
