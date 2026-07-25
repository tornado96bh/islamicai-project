from __future__ import annotations
from sqlalchemy import select
from packages.database.models import Author
from .base import BaseRepository

class AuthorRepository(BaseRepository[Author]):
    model_cls = Author
    def get_by_name(self, name: str):
        return self.db.scalar(select(Author).where(Author.name == name))
    def search(self, text: str):
        return list(self.db.scalars(select(Author).where(Author.name.ilike(f"%{text}%")).order_by(Author.name)).all())
