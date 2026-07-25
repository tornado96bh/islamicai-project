"""Initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-07-24 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("authors",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=500), nullable=True),
        sa.Column("kunya", sa.String(length=255), nullable=True),
        sa.Column("birth_year_hijri", sa.Integer(), nullable=True),
        sa.Column("death_year_hijri", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_authors")),
    )
    op.create_index(op.f("ix_authors_name"), "authors", ["name"], unique=False)

    op.create_table("researchers",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=500), nullable=True),
        sa.Column("kunya", sa.String(length=255), nullable=True),
        sa.Column("birth_year_hijri", sa.Integer(), nullable=True),
        sa.Column("death_year_hijri", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_researchers")),
    )
    op.create_index(op.f("ix_researchers_name"), "researchers", ["name"], unique=False)

    op.create_table("publishers",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publishers")),
        sa.UniqueConstraint("name", name=op.f("uq_publishers_name")),
    )
    op.create_index(op.f("ix_publishers_name"), "publishers", ["name"], unique=False)

    op.create_table("books",
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("short_title", sa.String(length=255), nullable=True),
        sa.Column("original_title", sa.String(length=500), nullable=True),
        sa.Column("slug", sa.String(length=500), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("isbn", sa.String(length=50), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_books")),
        sa.UniqueConstraint("slug", name=op.f("uq_books_slug")),
    )
    op.create_index(op.f("ix_books_isbn"), "books", ["isbn"], unique=False)
    op.create_index(op.f("ix_books_language"), "books", ["language"], unique=False)
    op.create_index(op.f("ix_books_slug"), "books", ["slug"], unique=False)
    op.create_index(op.f("ix_books_title"), "books", ["title"], unique=False)

    op.create_table("book_authors",
        sa.Column("book_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"], name=op.f("fk_book_authors_author_id_authors"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], name=op.f("fk_book_authors_book_id_books"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("book_id", "author_id", name=op.f("pk_book_authors")),
    )

    op.create_table("book_researchers",
        sa.Column("book_id", sa.Uuid(), nullable=False),
        sa.Column("researcher_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], name=op.f("fk_book_researchers_book_id_books"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["researcher_id"], ["researchers.id"], name=op.f("fk_book_researchers_researcher_id_researchers"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("book_id", "researcher_id", name=op.f("pk_book_researchers")),
    )

    op.create_table("book_publishers",
        sa.Column("book_id", sa.Uuid(), nullable=False),
        sa.Column("publisher_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], name=op.f("fk_book_publishers_book_id_books"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["publisher_id"], ["publishers.id"], name=op.f("fk_book_publishers_publisher_id_publishers"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("book_id", "publisher_id", name=op.f("pk_book_publishers")),
    )

    op.create_table("editions",
        sa.Column("book_id", sa.Uuid(), nullable=False),
        sa.Column("edition_number", sa.Integer(), nullable=False),
        sa.Column("publisher_name", sa.String(length=255), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("isbn", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], name=op.f("fk_editions_book_id_books"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_editions")),
    )
    op.create_index(op.f("ix_editions_book_id"), "editions", ["book_id"], unique=False)

    op.create_table("volumes",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], name=op.f("fk_volumes_edition_id_editions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_volumes")),
    )
    op.create_index(op.f("ix_volumes_edition_id"), "volumes", ["edition_id"], unique=False)

    op.create_table("pages",
        sa.Column("volume_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["volume_id"], ["volumes.id"], name=op.f("fk_pages_volume_id_volumes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
    )
    op.create_index(op.f("ix_pages_page_number"), "pages", ["page_number"], unique=False)
    op.create_index(op.f("ix_pages_volume_id"), "pages", ["volume_id"], unique=False)

    op.create_table("page_images",
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("image_path", sa.String(length=1000), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("dpi", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], name=op.f("fk_page_images_page_id_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_images")),
    )
    op.create_index(op.f("ix_page_images_page_id"), "page_images", ["page_id"], unique=False)

    op.create_table("page_elements",
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("element_type", sa.String(length=50), nullable=False),
        sa.Column("element_order", sa.Integer(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], name=op.f("fk_page_elements_page_id_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_elements")),
    )
    op.create_index(op.f("ix_page_elements_element_type"), "page_elements", ["element_type"], unique=False)
    op.create_index(op.f("ix_page_elements_page_id"), "page_elements", ["page_id"], unique=False)

def downgrade() -> None:
    op.drop_index(op.f("ix_page_elements_page_id"), table_name="page_elements")
    op.drop_index(op.f("ix_page_elements_element_type"), table_name="page_elements")
    op.drop_table("page_elements")
    op.drop_index(op.f("ix_page_images_page_id"), table_name="page_images")
    op.drop_table("page_images")
    op.drop_index(op.f("ix_pages_volume_id"), table_name="pages")
    op.drop_index(op.f("ix_pages_page_number"), table_name="pages")
    op.drop_table("pages")
    op.drop_index(op.f("ix_volumes_edition_id"), table_name="volumes")
    op.drop_table("volumes")
    op.drop_index(op.f("ix_editions_book_id"), table_name="editions")
    op.drop_table("editions")
    op.drop_table("book_publishers")
    op.drop_table("book_researchers")
    op.drop_table("book_authors")
    op.drop_index(op.f("ix_books_title"), table_name="books")
    op.drop_index(op.f("ix_books_slug"), table_name="books")
    op.drop_index(op.f("ix_books_language"), table_name="books")
    op.drop_index(op.f("ix_books_isbn"), table_name="books")
    op.drop_table("books")
    op.drop_index(op.f("ix_publishers_name"), table_name="publishers")
    op.drop_table("publishers")
    op.drop_index(op.f("ix_researchers_name"), table_name="researchers")
    op.drop_table("researchers")
    op.drop_index(op.f("ix_authors_name"), table_name="authors")
    op.drop_table("authors")
