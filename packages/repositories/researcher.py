from __future__ import annotations
from sqlalchemy import select
from packages.database.models import Researcher
from .base import BaseRepository

class ResearcherRepository(BaseRepository[Researcher]):
    model_cls = Researcher
    def get_by_name(self, name: str):
        return self.db.scalar(select(Researcher).where(Researcher.name == name))
    def search(self, text: str):
        return list(self.db.scalars(select(Researcher).where(Researcher.name.ilike(f"%{text}%")).order_by(Researcher.name)).all())
