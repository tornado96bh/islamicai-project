"""add_postgresql_fulltext_search

Revision ID: 435a5e5f0c67
Revises: 67da4bd2c0dd
"""

from typing import Sequence, Union

from alembic import op

revision: str = "435a5e5f0c67"
down_revision: Union[str, Sequence[str], None] = "67da4bd2c0dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_page_elements_text_fts
        ON page_elements
        USING GIN (
            to_tsvector('simple', coalesce(text, ''))
        );
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS ix_page_elements_text_fts;
    """)
