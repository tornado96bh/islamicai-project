from __future__ import annotations
from uuid import UUID
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel

class Volume(BaseModel):
    __tablename__ = "volumes"
    edition_id: Mapped[UUID] = mapped_column(ForeignKey("editions.id", ondelete="CASCADE"), nullable=False, index=True)
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edition: Mapped["Edition"] = relationship(back_populates="volumes")
    pages: Mapped[list["Page"]] = relationship(back_populates="volume", cascade="all, delete-orphan", lazy="selectin")
