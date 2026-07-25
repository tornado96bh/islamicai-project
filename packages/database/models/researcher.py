from __future__ import annotations
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel

class Researcher(BaseModel):
    __tablename__ = "researchers"
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kunya: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_year_hijri: Mapped[int | None] = mapped_column(Integer, nullable=True)
    death_year_hijri: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    books: Mapped[list["Book"]] = relationship(secondary="book_researchers", back_populates="researchers", lazy="selectin")
