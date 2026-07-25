from __future__ import annotations
from uuid import UUID
from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel

class PageElement(BaseModel):
    __tablename__ = "page_elements"
    page_id: Mapped[UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    element_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    element_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped["Page"] = relationship(back_populates="elements")
