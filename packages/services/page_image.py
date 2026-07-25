from __future__ import annotations

from sqlalchemy.orm import Session

from packages.repositories import PageImageRepository
from .base import BaseService


class PageImageService(BaseService[PageImageRepository]):
    def __init__(self, db: Session):
        super().__init__(db, PageImageRepository(db))

    def create(self, **kwargs):
        return self.repository.create(**kwargs)

    def get(self, id):
        return self.repository.get(id)

    def by_page(self, page_id):
        return self.repository.by_page(page_id)

    def all(self):
        return self.repository.all()
