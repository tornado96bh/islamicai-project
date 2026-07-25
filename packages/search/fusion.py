"""
Reciprocal Rank Fusion — دمج نتائج المحركات المتعددة.

المشكلة التي يحلها:

`ranking.py` كان يجمع درجات ثلاثة مقاييس غير متجانسة جمعاً خاماً:

    bucket["score"] += float(hit.get("score", 0.0))

و`ts_rank_cd` غير محدود الأعلى، و`similarity` من 0 إلى 1، وجيب التمام
من 0 إلى 1. وأسوأ: المحرك يبحث بثمانية استعلامات مرشّحة، فكل مطابقة
جديدة لنفس العنصر تضيف درجة أخرى. النتيجة المرصودة فعلياً:

    "text": ". الله"  ->  score 8.93  (hit_count = 8)

جزء نص من حرفين يتصدّر النتائج لأنه طابق ثمانية استعلامات.

الحل: RRF يتجاهل الدرجات الخام تماماً ويستعمل **الرتبة** فقط:

    score(d) = Σ  1 / (k + rank_i(d))

فمساهمة كل محرك محدودة بـ 1/(k+1) مهما كان مقياسه، وتكرار المطابقة
لنفس الاستعلام لا يراكم. هذا معيار مستقر في أدبيات الاسترجاع ولا
يحتاج معايرة أوزان يدوية.

المرجع: Cormack, Clarke & Buettcher (2009), k=60 هي القيمة المعتادة.

schema_version: 1.0.0
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

FUSION_VERSION = "1.0.0"
DEFAULT_K = 60

# أوزان المحركات. تُضرب في مساهمة RRF، ومجالها ضيق عمداً حتى لا يعود
# ضبط الأوزان اليدوي هو ما يحكم الترتيب.
DEFAULT_SOURCE_WEIGHTS = {
    "fts": 1.0,
    "fuzzy": 0.7,
    "semantic": 0.8,
}


@dataclass(slots=True)
class FusedHit:
    """نتيجة مدموجة مع تفسير كامل لسبب ترتيبها (الماستر §9)."""

    key: str
    payload: dict[str, Any]
    score: float = 0.0
    contributions: dict[str, float] = field(default_factory=dict)
    ranks: dict[str, int] = field(default_factory=dict)

    def explain(self) -> str:
        parts = [
            f"{src}: رتبة {self.ranks[src]} -> {self.contributions[src]:.4f}"
            for src in sorted(self.contributions)
        ]
        return " | ".join(parts)


def reciprocal_rank_fusion(
    runs: dict[str, list[dict[str, Any]]],
    *,
    key_fn: Callable[[dict], str],
    k: int = DEFAULT_K,
    weights: dict[str, float] | None = None,
) -> list[FusedHit]:
    """
    يدمج قوائم مرتّبة من محركات مختلفة.

    runs   : {"fts": [hit, ...], "fuzzy": [...], "semantic": [...]}
             كل قائمة مرتّبة تنازلياً بحسب جودة محركها.
    key_fn : يستخرج المعرّف الفريد من الـ hit.
    k      : ثابت التخميد. الأكبر يقلّل أثر الرتب الأولى.
    """
    weights = weights or DEFAULT_SOURCE_WEIGHTS
    fused: dict[str, FusedHit] = {}

    for source, hits in runs.items():
        weight = weights.get(source, 0.5)
        seen_in_run: set[str] = set()

        for rank, hit in enumerate(hits, start=1):
            key = key_fn(hit)
            # التكرار داخل نفس المحرك لا يراكم — هذا جوهر إصلاح العطب
            if key in seen_in_run:
                continue
            seen_in_run.add(key)

            contribution = weight / (k + rank)

            entry = fused.get(key)
            if entry is None:
                entry = FusedHit(key=key, payload=dict(hit))
                fused[key] = entry

            entry.score += contribution
            entry.contributions[source] = contribution
            entry.ranks[source] = rank

    return sorted(fused.values(), key=lambda x: x.score, reverse=True)


def exact_form_boost(
    hits: Iterable[FusedHit],
    *,
    query_raw: str,
    query_normalized: str,
    raw_text_fn: Callable[[dict], str],
    normalized_text_fn: Callable[[dict], str],
    boost: float = 0.5,
) -> list[FusedHit]:
    """
    يرجّح المطابقة بالصورة الأصلية على المطابقة بالصورة المطبّعة.

    هذا هو حل مشكلة "زرارة":

        زرارة  (الراوي، ابن أعين)
        زراره  (زر القميص)

    التطبيع يوحّدهما فيرتفع الاستدعاء (recall) ويسقط التمييز. الحل ليس
    إلغاء التطبيع — فحينها تضيع كل نتيجة كُتبت بالصورة الأخرى في طبعة
    مختلفة — بل الاحتفاظ بالاثنين وترجيح من طابق حرفياً.

    من يطابق "زرارة" بشكلها الأصلي يتقدّم على من يطابق "زراره" فقط.
    """
    out = []
    q_raw = (query_raw or "").strip()

    for hit in hits:
        raw = raw_text_fn(hit.payload) or ""
        norm = normalized_text_fn(hit.payload) or ""

        if q_raw and q_raw in raw:
            # مطابقة بالصورة الأصلية بحركاتها وهمزاتها
            hit.score += boost
            hit.contributions["exact_raw"] = boost
        elif query_normalized and query_normalized in norm:
            # مطابقة بالصورة المطبّعة فقط
            hit.score += boost * 0.3
            hit.contributions["exact_normalized"] = boost * 0.3

        out.append(hit)

    return sorted(out, key=lambda x: x.score, reverse=True)


def length_penalty(
    hits: Iterable[FusedHit],
    *,
    text_fn: Callable[[dict], str],
    min_words: int = 3,
    penalty: float = 0.4,
) -> list[FusedHit]:
    """
    يخفّض الشظايا القصيرة جداً.

    ". الله" أو "الله )2( ." ليست نتائج مفيدة لباحث، لكنها تحصل على
    تشابه trigram عالٍ لقصرها. الخفض نسبي لا إقصاء، حتى لا تضيع
    نتيجة قصيرة صحيحة فعلاً.
    """
    out = []
    for hit in hits:
        words = len((text_fn(hit.payload) or "").split())
        if words < min_words:
            factor = max(0.1, words / max(min_words, 1))
            reduction = hit.score * penalty * (1 - factor)
            hit.score -= reduction
            hit.contributions["short_penalty"] = -reduction
        out.append(hit)
    return sorted(out, key=lambda x: x.score, reverse=True)


__all__ = [
    "DEFAULT_K",
    "DEFAULT_SOURCE_WEIGHTS",
    "FUSION_VERSION",
    "FusedHit",
    "exact_form_boost",
    "length_penalty",
    "reciprocal_rank_fusion",
]
