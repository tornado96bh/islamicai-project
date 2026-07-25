from __future__ import annotations
from sqlalchemy.orm import Session
from packages.repositories import BookRepository
from .base import BaseService
class BookService(BaseService[BookRepository]):
    def __init__(self, db: Session): super().__init__(db, BookRepository(db))
    def create(self, **kwargs): return self.repository.create(**kwargs)
    def get(self, id): return self.repository.get(id)
    def slug(self, slug): return self.repository.get_by_slug(slug)
    def isbn(self, isbn): return self.repository.get_by_isbn(isbn)
    def search(self, text): return self.repository.search_title(text)
    def language(self, language): return self.repository.by_language(language)
    def all(self): return self.repository.all()
