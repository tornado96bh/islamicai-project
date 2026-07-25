from __future__ import annotations
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel

class Publisher(BaseModel):
    __tablename__ = "publishers"
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    books: Mapped[list["Book"]] = relationship(secondary="book_publishers", back_populates="publishers", lazy="selectin")
