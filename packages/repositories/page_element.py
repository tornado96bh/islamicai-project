from __future__ import annotations

from sqlalchemy import select

from packages.database.models import PageElement
from .base import BaseRepository


class PageElementRepository(BaseRepository[PageElement]):
    model_cls = PageElement

    def by_page(self, page_id):
        stmt = select(PageElement).where(PageElement.page_id == page_id).order_by(PageElement.element_order)
        return list(self.db.scalars(stmt).all())

    def by_type(self, element_type: str):
        stmt = select(PageElement).where(PageElement.element_type == element_type)
        return list(self.db.scalars(stmt).all())
