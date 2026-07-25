"""
Fuzzy Searcher — يقرأ من العمود المطبّع ويستعمل فهرس trigram فعلياً.

سياق الإصلاح
------------
النسخة السابقة كانت تستعلم على تعبير محسوب:
    similarity(translate(coalesce(text,''), ...), q) >= 0.18
ولا فهرس trigram على page_elements، فكان كل بحث مسحاً تسلسلياً.
وحتى مع الفهرس، دالة similarity() لا تستطيع استعماله — المعامل %
وحده يستفيد من فهرس GIN trigram.

عطب النسخة 2.0.0 (مُصلَح هنا)
-----------------------------
كان الضبط يتم بـ:
    SET LOCAL pg_trgm.similarity_threshold = :t
وأمر SET في PostgreSQL **لا يقبل معاملات مربوطة**. ففشل الأمر، ودخلت
المعاملة حالة abort، و except: pass ابتلع استثناء بايثون دون أن ينظّف
المعاملة — فسقط كل استعلام بعده بـ InFailedSqlTransaction.

الإصلاح:
  1. الضبط عبر الدالة set_limit() التي تقبل معاملاً فعلاً.
  2. تنفيذه داخل SAVEPOINT، فإن فشل لا يفسد المعاملة الأم.
  3. التحقق من نجاح الضبط بـ show_limit()، وعند الفشل يُستعمل مسار
     احتياطي بـ similarity() — أبطأ لكنه صحيح، ولا يرجّع صفر نتائج
     بصمت بسبب العتبة الافتراضية 0.3.

schema_version: 2.0.1
"""

from __future__ import annotations

import logging

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from packages.database.models import Edition, Page, PageElement, Volume
from packages.learning.dictionary import search_form_text

from .models import build_element_hit, hit_key

logger = logging.getLogger(__name__)

DIACRITICS = "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670\u0640"

DEFAULT_THRESHOLD = 0.18
FUZZY_VERSION = "2.0.1"


class FuzzySearcher:
    def __init__(self, db: Session, threshold: float = DEFAULT_THRESHOLD):
        self.db = db
        self.threshold = float(threshold)
        self._checked = False
        # هل نستطيع استعمال المعامل % (ومعه الفهرس)؟
        self.use_index_operator = True

    # -----------------------------------------------------------------
    def _prepare(self) -> None:
        """
        يضبط عتبة المعامل % مرة واحدة لكل جلسة.

        كل خطوة داخل SAVEPOINT مستقل، فأي فشل هنا لا يجهض المعاملة
        التي يعمل فيها بقية التطبيق.
        """
        if self._checked:
            return
        self._checked = True

        # 1) محاولة الضبط
        try:
            with self.db.begin_nested():
                self.db.execute(select(func.set_limit(self.threshold)))
        except Exception as exc:
            logger.warning("تعذّر ضبط عتبة pg_trgm عبر set_limit: %s", exc)

        # 2) التحقق الفعلي من العتبة السارية
        try:
            with self.db.begin_nested():
                current = self.db.execute(select(func.show_limit())).scalar()
            if current is not None and float(current) <= self.threshold + 1e-6:
                self.use_index_operator = True
                logger.info("عتبة pg_trgm = %s، المعامل %% مفعّل", current)
            else:
                self.use_index_operator = False
                logger.warning(
                    "العتبة السارية %s أعلى من المطلوبة %s — التحوّل إلى "
                    "المسار الاحتياطي بـ similarity() (أبطأ لكنه لا يفقد نتائج)",
                    current,
                    self.threshold,
                )
        except Exception as exc:
            self.use_index_operator = False
            logger.warning("تعذّر قراءة عتبة pg_trgm: %s — المسار الاحتياطي", exc)

    # -----------------------------------------------------------------
    def search(self, query: str, limit: int = 20) -> list[dict]:
        q = search_form_text(query)
        if not q:
            return []

        self._prepare()

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
        )

        if self.use_index_operator:
            # المعامل % هو ما يستعمل فهرس GIN trigram
            stmt = stmt.where(column.op("%")(q))
        else:
            # مسار احتياطي: صحيح لكنه لا يستفيد من الفهرس
            stmt = stmt.where(score_expr >= self.threshold)

        stmt = stmt.order_by(
            desc(score_expr), PageElement.page_id, PageElement.element_order
        ).limit(limit)

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

    # -----------------------------------------------------------------
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
