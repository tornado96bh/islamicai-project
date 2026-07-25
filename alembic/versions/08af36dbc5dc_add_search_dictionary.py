"""add_search_dictionary

Revision ID: 08af36dbc5dc
Revises: 435a5e5f0c67
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "08af36dbc5dc"
down_revision: Union[str, Sequence[str], None] = "435a5e5f0c67"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "search_dictionary",

        sa.Column("id", sa.UUID(), nullable=False),

        sa.Column("word", sa.Text(), nullable=False),

        sa.Column("frequency", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("document_frequency", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("first_seen_book", sa.UUID(), nullable=True),

        sa.Column("last_seen_book", sa.UUID(), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),

        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint("word")
    )

    op.create_index(
        "ix_search_dictionary_word",
        "search_dictionary",
        ["word"],
        unique=True
    )

    op.execute("""

    CREATE INDEX ix_search_dictionary_trgm

    ON search_dictionary

    USING gin (word gin_trgm_ops);

    """)


def downgrade() -> None:

    op.execute("DROP INDEX IF EXISTS ix_search_dictionary_trgm")

    op.drop_index("ix_search_dictionary_word", table_name="search_dictionary")

    op.drop_table("search_dictionary")
