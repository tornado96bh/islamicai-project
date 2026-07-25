from __future__ import annotations
from sqlalchemy import Column, ForeignKey, Table
from packages.database.base import Base

book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)
book_researchers = Table(
    "book_researchers",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("researcher_id", ForeignKey("researchers.id", ondelete="CASCADE"), primary_key=True),
)
book_publishers = Table(
    "book_publishers",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("publisher_id", ForeignKey("publishers.id", ondelete="CASCADE"), primary_key=True),
)
