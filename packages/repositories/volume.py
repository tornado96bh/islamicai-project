from __future__ import annotations
from sqlalchemy import select
from packages.database.models import Volume
from .base import BaseRepository

class VolumeRepository(BaseRepository[Volume]):
    model_cls = Volume
    def by_edition(self, edition_id):
        return list(self.db.scalars(select(Volume).where(Volume.edition_id == edition_id).order_by(Volume.volume_number)).all())
