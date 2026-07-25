from __future__ import annotations

from sqlalchemy import select

from packages.database.models import PageImage
from .base import BaseRepository


class PageImageRepository(BaseRepository[PageImage]):
    model_cls = PageImage

    def by_page(self, page_id):
        stmt = select(PageImage).where(PageImage.page_id == page_id)
        return list(self.db.scalars(stmt).all())
