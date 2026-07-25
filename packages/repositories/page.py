from __future__ import annotations

from sqlalchemy import select

from packages.database.models import Page
from .base import BaseRepository


class PageRepository(BaseRepository[Page]):
    model_cls = Page

    def by_volume(self, volume_id):
        stmt = select(Page).where(Page.volume_id == volume_id).order_by(Page.page_number)
        return list(self.db.scalars(stmt).all())

    def page(self, volume_id, number):
        stmt = select(Page).where(
            Page.volume_id == volume_id,
            Page.page_number == number,
        )
        return self.db.scalar(stmt)
