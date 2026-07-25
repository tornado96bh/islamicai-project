from __future__ import annotations
from uuid import UUID
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel

class Edition(BaseModel):
    __tablename__ = "editions"
    book_id: Mapped[UUID] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    edition_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    publisher_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    book: Mapped["Book"] = relationship(back_populates="editions")
    volumes: Mapped[list["Volume"]] = relationship(back_populates="edition", cascade="all, delete-orphan", lazy="selectin")
