from __future__ import annotations
from sqlalchemy.orm import Session
from packages.repositories import PublisherRepository
from .base import BaseService
class PublisherService(BaseService[PublisherRepository]):
    def __init__(self, db: Session): super().__init__(db, PublisherRepository(db))
    def create(self, **kwargs): return self.repository.create(**kwargs)
    def get(self, id): return self.repository.get(id)
    def search(self, text): return self.repository.search(text)
