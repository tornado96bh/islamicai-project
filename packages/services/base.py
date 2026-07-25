from __future__ import annotations
from typing import Generic, TypeVar
from sqlalchemy.orm import Session

RepositoryType = TypeVar("RepositoryType")

class BaseService(Generic[RepositoryType]):
    def __init__(self, db: Session, repository: RepositoryType):
        self.db = db
        self.repository = repository
    def commit(self): self.db.commit()
    def rollback(self): self.db.rollback()
    def flush(self): self.db.flush()
