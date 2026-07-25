"""
ReRanker — النسخة الثانية، متوافقة مع مقياس RRF.

العطب المُصلَح هنا
------------------
النسخة السابقة كانت تضيف boost بعد الترتيب:

    boost = sim * 0.95                     # sim من embeddings وهمية
    if query_form in search_text: boost += 0.40
    for phrase in phrases[:4]:    boost += 0.15
    item["score"] += boost

القياس على بيانات حقيقية أظهر أن هذا يضيف ~1.235 بينما أساس RRF
0.016 — أي أن معيد الترتيب كان يضاعف الأساس **23 مرة** ويقرر الترتيب
وحده. وبما أن EmbeddingBuilder هو hashing وهمي بـ 256 بُعداً
(تشابه "النبي محمد" و"الرسول الكريم" = 0.0000)، فالترتيب الفعلي كان
يحكمه ضجيج.

المبدأ في هذه النسخة
--------------------
1. مساهمة معيد الترتيب تبقى في حجم أساس RRF (أعشار الأجزاء من المئة)
   لا أضعافه. المقياس الواحد المتجانس شرط لأي ترتيب مفهوم.
2. الإشارات المعجمية (تطابق الاستعلام، العبارات) تبقى لأنها إشارة
   حقيقية. أما تشابه الـ embeddings فوزنه صفر افتراضياً حتى يُستبدل
   بنموذج حقيقي — إدخال ضجيج موزون أسوأ من عدم إدخاله.
3. كل مساهمة تُسجَّل في score_explain. لا تعديل صامت على الدرجة.

schema_version: 2.0.0
"""

from __future__ import annotations

import logging

from packages.learning.dictionary import search_form_text

logger = logging.getLogger(__name__)

RERANKER_VERSION = "2.0.0"

# وزن تشابه الـ embeddings. صفر عمداً: EmbeddingBuilder الحالي
# hashing بـ 256 بُعداً بلا أي فهم دلالي. ارفعه فقط بعد استبداله
# بنموذج حقيقي وإثبات التحسّن على المجموعة الذهبية.
EMBEDDING_WEIGHT = 0.0

# سقوف الإشارات المعجمية — في حجم أساس RRF (~0.01 إلى 0.03)
EXACT_QUERY_BONUS = 0.010
PHRASE_BONUS = 0.004
MAX_PHRASE_BONUS = 0.012


class ReRanker:
    def __init__(self, *, embedding_weight: float = EMBEDDING_WEIGHT):
        self.embedding_weight = float(embedding_weight)
        self.version = RERANKER_VERSION
        self.embedding = None

        if self.embedding_weight > 0:
            try:
                from packages.learning.embeddings import EmbeddingBuilder

                self.embedding = EmbeddingBuilder(dimension=256)
                logger.warning(
                    "معيد الترتيب يستعمل embeddings بوزن %s — تأكد أنه نموذج "
                    "حقيقي لا hashing، وإلا فأنت ترجّح بالضجيج",
                    self.embedding_weight,
                )
            except Exception as exc:
                logger.warning("تعذّر تحميل الـ embeddings: %s", exc)
                self.embedding = None

    # -----------------------------------------------------------------
    def _document_text(self, item: dict) -> str:
        parts = [
            item.get("book_title") or "",
            item.get("best_snippet") or item.get("snippet") or "",
            item.get("best_text") or item.get("text") or "",
        ]
        return " ".join(p for p in parts if p).strip()

    def rerank(self, search_query, bundle: dict) -> dict:
        query_form = (
            search_query.search_form
            or search_query.normalized
            or search_query.original
            or ""
        )
        qvec = None
        if self.embedding is not None and self.embedding_weight > 0:
            qvec = self.embedding.vectorize_text(query_form)

        for item in bundle.get("results", []):
            doc = self._document_text(item)
            if not doc:
                continue

            boost = 0.0
            detail: dict[str, float] = {}

            if qvec is not None:
                dvec = self.embedding.vectorize_text(doc)
                sim = float(self.embedding.similarity(qvec, dvec))
                contribution = sim * self.embedding_weight
                boost += contribution
                detail["rerank_embedding"] = round(contribution, 6)

            search_text = search_form_text(doc)

            if query_form and query_form in search_text:
                boost += EXACT_QUERY_BONUS
                detail["rerank_exact_query"] = EXACT_QUERY_BONUS

            phrases = getattr(search_query, "phrases", None) or []
            phrase_boost = 0.0
            for phrase in phrases[:4]:
                if phrase and phrase in search_text:
                    phrase_boost += PHRASE_BONUS
            phrase_boost = min(phrase_boost, MAX_PHRASE_BONUS)
            if phrase_boost:
                boost += phrase_boost
                detail["rerank_phrases"] = round(phrase_boost, 6)

            item["score"] = round(float(item.get("score", 0.0)) + boost, 8)

            # كل مساهمة مسجَّلة — لا تعديل صامت (الماستر §9)
            explain = item.setdefault("score_explain", {})
            explain.update(detail)
            explain["rerank_total"] = round(boost, 6)
            explain["score_final"] = item["score"]
            item["reranker_version"] = self.version

        bundle["results"].sort(
            key=lambda x: (
                x["score"],
                len((x.get("best_text") or "").split()),
                x.get("page_number") or 0,
            ),
            reverse=True,
        )
        return bundle
