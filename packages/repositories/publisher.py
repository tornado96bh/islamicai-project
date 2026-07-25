from __future__ import annotations
from sqlalchemy import select
from packages.database.models import Publisher
from .base import BaseRepository

class PublisherRepository(BaseRepository[Publisher]):
    model_cls = Publisher
    def get_by_name(self, name: str):
        return self.db.scalar(select(Publisher).where(Publisher.name == name))
    def search(self, text: str):
        return list(self.db.scalars(select(Publisher).where(Publisher.name.ilike(f"%{text}%")).order_by(Publisher.name)).all())
