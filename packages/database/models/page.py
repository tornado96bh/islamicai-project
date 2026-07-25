from __future__ import annotations
from uuid import UUID
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel

class Page(BaseModel):
    __tablename__ = "pages"
    volume_id: Mapped[UUID] = mapped_column(ForeignKey("volumes.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    volume: Mapped["Volume"] = relationship(back_populates="pages")
    images: Mapped[list["PageImage"]] = relationship(back_populates="page", cascade="all, delete-orphan", lazy="selectin")
    elements: Mapped[list["PageElement"]] = relationship(back_populates="page", cascade="all, delete-orphan", lazy="selectin")
