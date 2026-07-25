"""
Full-Text Searcher — يقرأ من العمود المطبّع.

سبب التغيير: النسخة السابقة كانت تستعلم بـ

    to_tsvector('simple', translate(coalesce(text,''), <حركات>, ''))

بينما الفهرس منشأ على

    to_tsvector('simple', coalesce(text_normalized,''))

وPostgreSQL يطابق فهارس التعابير حرفياً، فلم يكن الفهرس يُستعمل
إطلاقاً، وكان كل بحث مسحاً تسلسلياً للجدول مع حساب to_tsvector لكل
صف — مضروباً في ثمانية استعلامات مرشّحة.

التعبير هنا مطابق تماماً لتعبير الفهرس.

احتياطي OR للاستعلامات متعددة الكلمات
-------------------------------------
websearch_to_tsquery يربط الكلمات بـ AND، فاستعلام مثل
"زرارة بن أعين" يتطلب وجود الكلمات الثلاث في العنصر نفسه. ومع تفكك
OCR ("محم د" بدل "محمد") و انقسام الأسطر، كثيراً ما لا يجتمعن، فيرجع
الاستعلام صفراً وتتولى الاستعلامات المرشّحة العامة فتغرق النتيجة.

الحل: عند خلوّ نتيجة AND، تُعاد المحاولة بـ OR مع وسم السبب، فتظهر
العناصر التي تحوي بعض الكلمات بدل لا شيء.
"""

from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from packages.database.models import Edition, Page, PageElement, Volume
from packages.learning.dictionary import search_form_text

from .models import build_element_hit, hit_key

# مُبقى للتوافق مع أي كود قديم يستورده
DIACRITICS = "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670\u0640"


def _indexed_text():
    """
    يجب أن يطابق تعبير الفهرس حرفاً بحرف:
        GIN (to_tsvector('simple', coalesce(text_normalized, '')))
    أي تعديل هنا يبطل استعمال الفهرس بصمت.
    """
    return func.coalesce(PageElement.text_normalized, "")


class FullTextSearcher:
    def __init__(self, db: Session):
        self.db = db

    def search(self, query: str, limit: int = 20) -> list[dict]:
        q = search_form_text(query)
        if not q:
            return []

        text_expr = _indexed_text()
        ts_vector = func.to_tsvector("simple", text_expr)
        ts_query = func.websearch_to_tsquery("simple", q)
        rank = func.ts_rank_cd(ts_vector, ts_query).label("score")

        stmt = (
            select(PageElement, rank)
            .options(
                joinedload(PageElement.page)
                .joinedload(Page.volume)
                .joinedload(Volume.edition)
                .joinedload(Edition.book)
            )
            .where(PageElement.text_normalized.isnot(None))
            .where(ts_vector.op("@@")(ts_query))
            .order_by(desc(rank), PageElement.page_id, PageElement.element_order)
            .limit(limit)
        )

        hits = self._run(stmt, "full text")

        # احتياطي OR: AND لم يجد شيئاً والاستعلام متعدد الكلمات
        words = [w for w in q.split() if w]
        if not hits and len(words) > 1:
            or_query = func.to_tsquery("simple", " | ".join(words))
            or_rank = func.ts_rank_cd(ts_vector, or_query).label("score")
            or_stmt = (
                select(PageElement, or_rank)
                .options(
                    joinedload(PageElement.page)
                    .joinedload(Page.volume)
                    .joinedload(Volume.edition)
                    .joinedload(Edition.book)
                )
                .where(PageElement.text_normalized.isnot(None))
                .where(ts_vector.op("@@")(or_query))
                .order_by(desc(or_rank), PageElement.page_id, PageElement.element_order)
                .limit(limit)
            )
            try:
                hits = self._run(or_stmt, "full text (or)")
            except Exception:
                hits = []

        return hits

    def _run(self, stmt, reason: str) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for element, score in self.db.execute(stmt).all():
            hit = build_element_hit(element, float(score or 0.0), "fts", reason)
            key = hit_key(hit)
            if key in seen:
                continue
            seen.add(key)
            out.append(hit)
        return out

    def search_many(self, queries: list[str], limit: int = 20) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for query in queries:
            for hit in self.search(query, limit=max(limit, 20)):
                key = hit_key(hit)
                if key in seen:
                    continue
                seen.add(key)
                out.append(hit)
        return out
