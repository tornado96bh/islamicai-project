from __future__ import annotations

from sqlalchemy.orm import Session

from packages.repositories.search import SearchRepository

class SearchService:
    def __init__(self, db: Session):
        self.repository = SearchRepository(db)

    def search(self, query: str, limit: int = 20, offset: int = 0):
        return self.repository.search(query=query, limit=limit, offset=offset)
