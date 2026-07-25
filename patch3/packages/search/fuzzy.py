"""
Fuzzy Searcher — يقرأ من العمود المطبّع ويستعمل فهرس trigram فعلياً.

سببا التغيير:

1. النسخة السابقة كانت تستعلم على تعبير محسوب:
       similarity(translate(coalesce(text,''), ...), q) >= 0.18
   ولا يوجد فهرس trigram على page_elements أصلاً، فكان كل بحث
   مسحاً تسلسلياً مع حساب التشابه لكل صف.

2. حتى مع وجود الفهرس، دالة similarity() لا تستطيع استعماله.
   المعامل % وحده هو ما يستفيد من فهرس GIN trigram. لذلك صار
   الترشيح بـ % والترتيب بـ similarity على الصفوف المرشّحة فقط.

عتبة التشابه تُضبط لكل جلسة عبر pg_trgm.similarity_threshold.
"""

from __future__ import annotations

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session, joinedload

from packages.database.models import Edition, Page, PageElement, Volume
from packages.learning.dictionary import search_form_text

from .models import build_element_hit, hit_key

DIACRITICS = "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670\u0640"

DEFAULT_THRESHOLD = 0.18


class FuzzySearcher:
    def __init__(self, db: Session, threshold: float = DEFAULT_THRESHOLD):
        self.db = db
        self.threshold = threshold
        self._threshold_set = False

    def _ensure_threshold(self) -> None:
        """
        يضبط عتبة المعامل % لهذه الجلسة.

        بدونها العتبة الافتراضية 0.3 وهي أعلى من عتبتنا، فتضيع نتائج.
        SET LOCAL يقتصر أثره على المعاملة الجارية.
        """
        if self._threshold_set:
            return
        try:
            self.db.execute(
                text("SET LOCAL pg_trgm.similarity_threshold = :t"),
                {"t": float(self.threshold)},
            )
            self._threshold_set = True
        except Exception:
            # لو فشل الضبط، الاستعلام يبقى صحيحاً بعتبة أعلى
            self._threshold_set = True

    def search(self, query: str, limit: int = 20) -> list[dict]:
        q = search_form_text(query)
        if not q:
            return []

        self._ensure_threshold()

        column = PageElement.text_normalized
        score_expr = func.greatest(
            func.similarity(column, q),
            func.word_similarity(q, column),
        ).label("score")

        stmt = (
            select(PageElement, score_expr)
            .options(
                joinedload(PageElement.page)
                .joinedload(Page.volume)
                .joinedload(Volume.edition)
                .joinedload(Edition.book)
            )
            .where(column.isnot(None))
            # المعامل % هو ما يستعمل فهرس GIN trigram؛ similarity() لا تفعل
            .where(column.op("%")(q))
            .order_by(desc(score_expr), PageElement.page_id, PageElement.element_order)
            .limit(limit)
        )

        hits: list[dict] = []
        seen: set[str] = set()
        for element, score in self.db.execute(stmt).all():
            hit = build_element_hit(element, float(score or 0.0), "fuzzy", "trigram")
            key = hit_key(hit)
            if key in seen:
                continue
            seen.add(key)
            hits.append(hit)
        return hits

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
