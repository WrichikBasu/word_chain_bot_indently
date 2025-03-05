"""wal-mode

Revision ID: 54a9a6fc599f
Revises: b9bee291a668
Create Date: 2025-02-26 08:53:26.732697

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '54a9a6fc599f'
down_revision: Union[str, None] = 'b9bee291a668'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # enable write ahead logging
        op.execute("PRAGMA journal_mode = WAL")
        #  best choice for WAL journal mode
        op.execute("PRAGMA synchronous = NORMAL")

def downgrade() -> None:
    with op.get_context().autocommit_block():
        # go back to default behaviour
        op.execute("PRAGMA journal_mode = DELETE")
        #  best choice for DELETE journal mode
        op.execute("PRAGMA synchronous = FULL")
