from __future__ import annotations

from sqlalchemy.orm import Session

from packages.repositories import PageRepository
from .base import BaseService


class PageService(BaseService[PageRepository]):
    def __init__(self, db: Session):
        super().__init__(db, PageRepository(db))

    def create(self, **kwargs):
        return self.repository.create(**kwargs)

    def get(self, id):
        return self.repository.get(id)

    def by_volume(self, volume_id):
        return self.repository.by_volume(volume_id)

    def page(self, volume_id, number):
        return self.repository.page(volume_id, number)

    def all(self):
        return self.repository.all()
