"""
Filters — عتبات نسبية بدل الأرقام السحرية.

العطب المُصلَح
--------------
النسخة السابقة كانت تقارن الدرجة بأرقام مطلقة:

    if score < result_score_threshold(intent):  # 0.10 / 0.14 / 0.15
    if score < 1.25:                            # عبارة عامة
    if score < 1.55:                            # لا تغطية للاستعلام

هذه الأرقام معايَرة على مقياس الترتيب القديم (مجاميع خام في نطاق
4 إلى 9). بعد الانتقال إلى RRF صارت الدرجات في نطاق 0.02 إلى 0.06،
فأي عتبة مطلقة تحذف كل النتائج أو لا تحذف شيئاً.

القياس كشف أن النتائج كانت تنجو بالصدفة: معيد الترتيب كان يضيف ~1.23
فترتفع فوق عتبة 1.25 بفارق ضئيل. أي تغيير في وزن معيد الترتيب كان
سيمسح النتائج كلها.

المبدأ الجديد
-------------
العتبات **نسبية إلى أعلى درجة في نفس الاستعلام**، لا مطلقة. فتبقى
سليمة مهما تغيّر مقياس الترتيب مستقبلاً (BGE-M3، Cross-Encoder ...).

schema_version: 2.0.0
"""

from __future__ import annotations

from typing import Any

from packages.learning.dictionary import search_form_text, tokenize_text

from .stopwords import is_generic_phrase

FILTERS_VERSION = "2.0.0"

# نِسَب من أعلى درجة في نتائج الاستعلام نفسه
MIN_RATIO_DEFAULT = 0.15
MIN_RATIO_GENERIC = 0.55      # عبارة عامة لا تطابق الاستعلام
MIN_RATIO_NO_COVERAGE = 0.70  # لا تقاطع كلمات إطلاقاً

# حد أدنى مطلق للعناصر الفارغة فقط
MIN_WORDS = 1


def _result_text(item: dict[str, Any]) -> str:
    return item.get("best_text") or item.get("text") or item.get("snippet") or ""


def _coverage(query_form: str, text: str) -> float:
    q = set(tokenize_text(search_form_text(query_form)))
    t = set(tokenize_text(search_form_text(text)))
    if not q:
        return 0.0
    return len(q & t) / len(q)


def relative_ratio(intent: str | None) -> float:
    """النسبة الدنيا المقبولة من أعلى درجة، بحسب نية الاستعلام."""
    if intent in {"person", "book", "entity"}:
        return 0.08
    if intent == "passage":
        return 0.12
    return MIN_RATIO_DEFAULT


def should_keep_result(
    item: dict[str, Any],
    query_form: str,
    intent: str | None,
    *,
    top_score: float = 0.0,
) -> bool:
    """
    top_score هو أعلى درجة في نفس مجموعة النتائج. تمريره صفراً يعطّل
    الترشيح النسبي ويُبقي كل ما ليس فارغاً — وهو سلوك آمن افتراضياً.
    """
    text = search_form_text(_result_text(item))
    if not text or len(text.split()) < MIN_WORDS:
        return False

    score = float(item.get("score", 0.0))

    if top_score <= 0:
        return True  # لا مرجع للمقارنة؛ لا نحذف شيئاً

    ratio = score / top_score

    if ratio < relative_ratio(intent):
        return False

    if is_generic_phrase(text) and query_form not in text:
        if ratio < MIN_RATIO_GENERIC:
            return False

    if query_form and query_form not in text and _coverage(query_form, text) == 0:
        if intent not in {"person", "book", "entity"} and ratio < MIN_RATIO_NO_COVERAGE:
            return False

    return True


def prune_results(
    results: list[dict[str, Any]],
    query_form: str,
    intent: str | None,
) -> list[dict[str, Any]]:
    if not results:
        return []

    top_score = max(float(r.get("score", 0.0)) for r in results)

    kept: list[dict[str, Any]] = []
    for item in results:
        if should_keep_result(item, query_form, intent, top_score=top_score):
            kept.append(item)
        else:
            # لا حذف صامت: يُسجَّل السبب لمن يفحص لاحقاً
            item["pruned_reason"] = "below_relative_threshold"

    # شبكة أمان: لا نرجّع صفر نتائج بينما توجد مطابقات
    if not kept and results:
        return results[: min(10, len(results))]

    return kept
