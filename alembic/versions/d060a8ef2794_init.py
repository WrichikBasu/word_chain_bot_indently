"""init

Revision ID: d060a8ef2794
Revises: 
Create Date: 2024-10-17 19:37:59.413168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd060a8ef2794'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE TABLE IF NOT EXISTS blacklist (server_id INT NOT NULL, words TEXT NOT NULL, PRIMARY KEY (server_id, words))')
    op.execute('CREATE TABLE IF NOT EXISTS whitelist (server_id INT NOT NULL, words TEXT NOT NULL, PRIMARY KEY (server_id, words))')
    op.execute('CREATE TABLE IF NOT EXISTS members (server_id INTEGER NOT NULL, member_id INTEGER NOT NULL, score INTEGER NOT NULL, correct INTEGER NOT NULL, wrong INTEGER NOT NULL, karma REAL NOT NULL, PRIMARY KEY (server_id, member_id))')
    op.execute('CREATE TABLE IF NOT EXISTS used_words (server_id INTEGER NOT NULL, words TEXT NOT NULL, PRIMARY KEY (server_id, words))')
    op.execute('CREATE TABLE IF NOT EXISTS word_cache (words TEXT PRIMARY KEY)')


def downgrade() -> None:
    op.execute('DROP TABLE blacklist')
    op.execute('DROP TABLE whitelist')
    op.execute('DROP TABLE members')
    op.execute('DROP TABLE used_words')
    op.execute('DROP TABLE word_cache')
