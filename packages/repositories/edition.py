from __future__ import annotations
from sqlalchemy import select
from packages.database.models import Edition
from .base import BaseRepository

class EditionRepository(BaseRepository[Edition]):
    model_cls = Edition
    def by_book(self, book_id):
        return list(self.db.scalars(select(Edition).where(Edition.book_id == book_id).order_by(Edition.edition_number)).all())
