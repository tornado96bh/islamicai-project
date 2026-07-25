from __future__ import annotations
from sqlalchemy.orm import Session
from packages.repositories import EditionRepository
from .base import BaseService
class EditionService(BaseService[EditionRepository]):
    def __init__(self, db: Session): super().__init__(db, EditionRepository(db))
    def create(self, **kwargs): return self.repository.create(**kwargs)
    def by_book(self, book_id): return self.repository.by_book(book_id)
