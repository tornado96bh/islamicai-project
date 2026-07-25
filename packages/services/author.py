from __future__ import annotations
from sqlalchemy.orm import Session
from packages.repositories import AuthorRepository
from .base import BaseService
class AuthorService(BaseService[AuthorRepository]):
    def __init__(self, db: Session): super().__init__(db, AuthorRepository(db))
    def create(self, **kwargs): return self.repository.create(**kwargs)
    def get(self, id): return self.repository.get(id)
    def search(self, text): return self.repository.search(text)
    def all(self): return self.repository.all()
