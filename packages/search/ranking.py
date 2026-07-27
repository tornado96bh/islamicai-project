"""
Ranking Engine — النسخة الثانية، قائمة على RRF.

سبب إعادة الكتابة: السطر التالي في النسخة السابقة

    bucket["score"] += float(hit.get("score", 0.0))

كان يجمع درجة جديدة في كل مرة يطابق فيها العنصرُ استعلاماً مرشّحاً
آخر. والمحرك يبحث بثمانية استعلامات مرشّحة، فشظية من حرفين طابقت
ثمانية منها جمعت ثماني درجات وتصدّرت النتائج:

    "text": ". الله"   score 8.93   hit_count 8

وأسوأ من التراكم أن المجموع يخلط ثلاثة مقاييس غير متجانسة:
ts_rank_cd غير محدود الأعلى، و similarity من 0 إلى 1، وجيب التمام
من 0 إلى 1.

البديل: RRF يتجاهل الدرجات الخام ويستعمل الرتبة داخل كل محرك.
مساهمة أي محرك محدودة بـ weight/(k+1) مهما كان مقياسه، والتكرار
داخل المحرك الواحد لا يراكم.

الإشارات الدلالية (تطابق حرفي، تقاطع كلمات، نية الاستعلام) بقيت
كما هي لكنها صارت **تعديلات** على أساس RRF لا بدائل عنه.

schema_version: 2.0.0
"""

from __future__ import annotations

from collections import Counter

from packages.learning.dictionary import search_form_text, tokenize_text

from .fusion import DEFAULT_K, DEFAULT_SOURCE_WEIGHTS
from .signals import DEFAULT_WEIGHTS as SIGNAL_WEIGHTS
from .signals import compute_signals

try:
    from packages.layout.classifier import layout_bonus

    HAS_LAYOUT = True
except ImportError:  # محرك التخطيط اختياري
    HAS_LAYOUT = False

    def layout_bonus(_):  # type: ignore[misc]
        return 0.0
from .models import hit_key

RANKING_VERSION = "2.3.0"

# عنصر بأقل من هذا العدد من الكلمات يُعدّ شظية ويُخفَّض
FRAGMENT_MIN_WORDS = 3


class RankingEngine:
    def __init__(self, *, k: int = DEFAULT_K):
        self.k = k
        self.source_weights = dict(DEFAULT_SOURCE_WEIGHTS)
        self.version = RANKING_VERSION

    # -- الإشارات الدلالية ------------------------------------------------

    def _graded_signals(self, search_query, bucket: dict) -> tuple[float, dict]:
        """
        إشارات متدرّجة تُحسب من النتيجة نفسها.

        الإشارات القديمة كانت ثنائية، فصارت في استعلام شائع مثل «الله»
        إزاحةً ثابتة (0.022 في كل النتائج العشرين) لا إشارةَ تمييز.
        هذه تتراوح بحسب جودة OCR وتغطية الاستعلام واكتمال الجملة.
        """
        query_tokens = list(
            search_query.search_tokens
            or tokenize_text(search_form_text(search_query.original or ""))
        )
        raw = bucket.get("best_text") or bucket.get("text") or ""
        norm = bucket.get("search_text") or search_form_text(raw)

        scores = compute_signals(
            raw_text=raw, normalized_text=norm, query_tokens=query_tokens
        )
        return scores.weighted(SIGNAL_WEIGHTS), scores.as_dict()

    def _signal_bonus(self, search_query, intent, bucket: dict) -> float:
        """
        تعديلات دلالية فوق أساس RRF.

        المجال هنا ضيق عمداً (أقصى ~0.05) لأن أساس RRF نفسه في حدود
        0.01–0.03. لو تُركت المكافآت بقيمها القديمة (3.0, 1.7 ...)
        لابتلعت الأساس وعاد الترتيب إلى ضبط أوزان يدوي.
        """
        query_form = (
            search_query.search_form
            or search_query.normalized
            or search_query.original
            or ""
        )
        search_text = search_form_text(bucket.get("best_text") or bucket.get("text") or "")
        query_tokens = set(
            search_query.search_tokens
            or tokenize_text(search_form_text(search_query.original or ""))
        )

        bonus = 0.0

        # مطابقة تامة للصيغة البحثية
        if query_form and search_text == query_form:
            bonus += 0.030
        elif query_form and query_form in search_text:
            bonus += 0.012

        # تقاطع الكلمات، بسقف حتى لا يفوز النص الطويل بالطول وحده
        overlap = len(set(tokenize_text(search_text)) & query_tokens)
        bonus += min(overlap, 6) * 0.002

        # اتفاق المحركات
        sources = set(bucket.get("sources") or [])
        bonus += min(len(sources), 3) * 0.004

        # النية
        if intent and getattr(intent, "label", None):
            label = intent.label
            if label == "hadith" and any(k in search_text for k in ("قال", "عن", "حدث", "روي")):
                bonus += 0.004
            elif label == "quran" and any(k in search_text for k in ("ايه", "سوره", "القران", "المصحف")):
                bonus += 0.006
            elif label == "bibliography" and any(k in search_text for k in ("كتاب", "مجلد", "جزء", "باب")):
                bonus += 0.004

        return bonus

    def _exact_raw_bonus(self, search_query, bucket: dict) -> float:
        """
        ترجيح المطابقة بالصورة الأصلية على المطبّعة — حل مشكلة «زرارة».

        زرارة (الراوي) و زراره (زر القميص) يتوحّدان بعد التطبيع. من
        طابق الصورة الأصلية بحركاتها وهمزاتها يتقدّم.
        """
        raw_query = (search_query.original or "").strip()
        if not raw_query:
            return 0.0
        raw_text = bucket.get("best_text") or bucket.get("text") or ""
        return 0.020 if raw_query in raw_text else 0.0

    def _fragment_penalty(self, bucket: dict, base: float) -> float:
        """
        يخفّض الشظايا القصيرة.

        ". الله" ليست نتيجة مفيدة لباحث، لكنها تنال تشابه trigram
        عالياً لقصرها. الخفض نسبي لا إقصاء، حتى لا تضيع نتيجة قصيرة
        صحيحة فعلاً.
        """
        words = len((bucket.get("best_text") or bucket.get("text") or "").split())
        if words >= FRAGMENT_MIN_WORDS:
            return 0.0
        factor = max(0.1, words / FRAGMENT_MIN_WORDS)
        return -base * 0.5 * (1 - factor)

    # -- الدمج -------------------------------------------------------------

    def rank(self, search_query, intent, context: dict, hits: list[dict]) -> dict:
        merged: dict[str, dict] = {}
        # الرتبة الحالية داخل كل محرك؛ الترتيب هو ترتيب الوصول
        rank_counter: dict[str, int] = {}
        # كل مفتاح يُحتسب مرة واحدة فقط لكل محرك
        seen_per_source: dict[str, set[str]] = {}

        for hit in hits:
            key = hit_key(hit)
            source = hit.get("source") or "unknown"

            seen = seen_per_source.setdefault(source, set())
            first_time_in_source = key not in seen

            if first_time_in_source:
                seen.add(key)
                rank_counter[source] = rank_counter.get(source, 0) + 1
                rank = rank_counter[source]
                weight = self.source_weights.get(source, 0.5)
                contribution = weight / (self.k + rank)
            else:
                # التكرار داخل نفس المحرك لا يراكم — جوهر الإصلاح
                contribution = 0.0
                rank = None

            bucket = merged.get(key)
            if bucket is None:
                bucket = dict(hit)
                bucket["score"] = contribution
                bucket["sources"] = [source]
                bucket["reasons"] = list(
                    hit.get("reasons") or ([hit["reason"]] if hit.get("reason") else [])
                )
                bucket["source_counts"] = Counter([source])
                bucket["hit_count"] = 1
                bucket["rrf_ranks"] = {source: rank} if rank else {}
                merged[key] = bucket
            else:
                bucket["score"] += contribution
                bucket["sources"].append(source)
                bucket["source_counts"][source] += 1
                if hit.get("reason"):
                    bucket["reasons"].append(hit["reason"])
                bucket["hit_count"] += 1
                if rank:
                    bucket.setdefault("rrf_ranks", {})[source] = rank

            # أفضل عنصر داخل الصفحة يُختار بدرجة محركه الخام، وهذا
            # سليم لأنه اختيار داخلي لا ترتيب بين النتائج
            raw = float(hit.get("score", 0.0) or 0.0)
            if hit.get("element_id") and (
                not bucket.get("best_element_id")
                or raw > float(bucket.get("best_element_score", 0.0))
            ):
                bucket["best_element_id"] = hit.get("element_id")
                bucket["best_element_type"] = hit.get("element_type")
                bucket["best_element_order"] = hit.get("element_order")
                bucket["best_text"] = hit.get("text")
                bucket["best_snippet"] = hit.get("snippet")
                bucket["best_element_score"] = raw

            if hit.get("element_id") is None and not bucket.get("best_text"):
                bucket["best_text"] = hit.get("text")
                bucket["best_snippet"] = hit.get("snippet")

        # -- التعديلات فوق أساس RRF ---------------------------------------
        ranked: list[dict] = []
        for bucket in merged.values():
            base = float(bucket["score"])
            explain = {"rrf_base": round(base, 6)}

            signal = self._signal_bonus(search_query, intent, bucket)
            graded, graded_detail = self._graded_signals(search_query, bucket)
            explain.update(graded_detail)
            exact = self._exact_raw_bonus(search_query, bucket)

            # ترجيح المتن على الهامش والترويسة الجارية.
            # قبل محرك التخطيط كان كل عنصر element_type="text"، فكانت
            # إحالات الهوامش تنافس المتن على صدارة النتائج.
            layout = layout_bonus(bucket.get("best_element_type")
                                  or bucket.get("element_type"))

            penalty = self._fragment_penalty(
                bucket, base + signal + graded + exact + layout
            )

            total = base + signal + graded + exact + layout + penalty
            explain["signals"] = round(signal, 6)
            explain["graded_signals"] = round(graded, 6)
            explain["exact_raw"] = round(exact, 6)
            explain["layout"] = round(layout, 6)
            explain["fragment_penalty"] = round(penalty, 6)

            bucket["score"] = round(max(total, 0.0), 8)
            bucket["score_explain"] = explain
            bucket["sources"] = sorted(set(bucket.get("sources") or []))
            bucket["reasons"] = sorted({r for r in bucket.get("reasons") or [] if r})
            bucket["source_counts"] = dict(bucket.get("source_counts") or {})
            bucket["search_text"] = search_form_text(
                bucket.get("best_text") or bucket.get("text") or ""
            )
            bucket["ranking_version"] = self.version
            ranked.append(bucket)

        ranked.sort(
            key=lambda x: (
                x["score"],
                len((x.get("best_text") or "").split()),
                x.get("page_number") or 0,
            ),
            reverse=True,
        )

        ranked = self._diversify(ranked)
        return {"count": len(ranked), "results": ranked}

    def _diversify(self, ranked: list[dict], max_per_page: int = 3) -> list[dict]:
        """
        يمنع صفحة واحدة من احتكار الصدارة.

        في مخرجاتك ظهرت الصفحة 41 مرتين والصفحة 240 مرتين ضمن العشرين
        الأولى. النتائج المتجاورة على صفحة واحدة تتشابه، فتزاحم تغطيةَ
        بقية الكتاب. المتجاوزة لا تُحذف بل تُؤخَّر.
        """
        seen: dict[str, int] = {}
        primary: list[dict] = []
        deferred: list[dict] = []

        for item in ranked:
            key = str(item.get("page_id") or "")
            count = seen.get(key, 0)
            if count < max_per_page:
                seen[key] = count + 1
                primary.append(item)
            else:
                item["deferred_reason"] = "page_diversity"
                deferred.append(item)

        return primary + deferred
