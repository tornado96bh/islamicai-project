from __future__ import annotations

from sqlalchemy.orm import Session

from packages.repositories import PageElementRepository
from .base import BaseService


class PageElementService(BaseService[PageElementRepository]):
    def __init__(self, db: Session):
        super().__init__(db, PageElementRepository(db))

    def create(self, **kwargs):
        return self.repository.create(**kwargs)

    def get(self, id):
        return self.repository.get(id)

    def by_page(self, page_id):
        return self.repository.by_page(page_id)

    def by_type(self, element_type: str):
        return self.repository.by_type(element_type)

    def all(self):
        return self.repository.all()
