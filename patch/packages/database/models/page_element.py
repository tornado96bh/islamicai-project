from __future__ import annotations
from uuid import UUID
from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel


class PageElement(BaseModel):
    """
    عنصر على صفحة.

    فصل النص إلى ثلاثة حقول تنفيذاً لعقد PageElement في packages/schemas:
      text_raw        : النص كما استُخرج، بتشكيله وهمزاته. مصدر الاستشهاد.
      text_normalized : الصيغة البحثية. هذا ما يُفهرَس ويُبحث فيه.
      text            : مُبقى للتوافق مع الكود القديم. لا تكتب فيه جديداً.
    """

    __tablename__ = "page_elements"

    page_id: Mapped[UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    element_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    element_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonicalizer_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    layout_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    page: Mapped["Page"] = relationship(back_populates="elements")
