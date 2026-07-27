from __future__ import annotations
from uuid import UUID
from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.database.base import BaseModel


class PageElement(BaseModel):
    """
    عنصر على صفحة.

    ثلاث صيغ للنص، لكل واحدة غرض لا يقوم غيرها مقامه:

      text_raw        الأصل كما استُخرج. مقدَّس: لا يُمس أبداً.
                      هذا مرجع الاستشهاد العلمي.
      text_display    مقروء: بلا تمديد ولا تفكّك، **بكل الحركات
                      والهمزات والنقاط**. هذا ما يُعرض للقارئ.
      text_normalized بحثي: بلا حركات، بألف موحّدة. هذا ما يُفهرَس.

    وتفكيك الرواية إلى رقم وسند ومتن، كلٌّ مقتطع حرفياً من الأصل.
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
    text_display: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonicalizer_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    hadith_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    isnad_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    matn_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    split_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    layout_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    page: Mapped["Page"] = relationship(back_populates="elements")
