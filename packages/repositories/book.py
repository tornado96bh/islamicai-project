from __future__ import annotations
from sqlalchemy import select
from packages.database.models import Book
from .base import BaseRepository

class BookRepository(BaseRepository[Book]):
    model_cls = Book
    def get_by_slug(self, slug: str):
        return self.db.scalar(select(Book).where(Book.slug == slug))
    def get_by_isbn(self, isbn: str):
        return self.db.scalar(select(Book).where(Book.isbn == isbn))
    def search_title(self, text: str):
        return list(self.db.scalars(select(Book).where(Book.title.ilike(f"%{text}%")).order_by(Book.title)).all())
    def by_language(self, language: str):
        return list(self.db.scalars(select(Book).where(Book.language == language).order_by(Book.title)).all())
