from __future__ import annotations
from sqlalchemy.orm import Session
from packages.repositories import VolumeRepository
from .base import BaseService
class VolumeService(BaseService[VolumeRepository]):
    def __init__(self, db: Session): super().__init__(db, VolumeRepository(db))
    def create(self, **kwargs): return self.repository.create(**kwargs)
    def by_edition(self, edition_id): return self.repository.by_edition(edition_id)
