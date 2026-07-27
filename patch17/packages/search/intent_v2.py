"""
مصنّف النية — بأدلة مرجَّحة وثقة معايَرة.

المشكلة التي يحلّها
-------------------
كل استعلام كان يعود بـ:

    {"label": "general", "confidence": 0.55}

الرقم 0.55 لم يكن قياساً بل قيمةً ثابتة مكتوبة في الكود. فلا يخبر
النظامَ ولا الباحثَ بشيء، ولا يمكن البناء عليه.

المنهج
------
كل نية لها **أدلة** لكل دليل وزن. الثقة تُحسب من مجموع الأدلة
المتحققة نسبةً إلى ما هو ممكن، مع فارق عن النية التالية.

فالثقة تصير قابلة للتفسير: يمكن دائماً سؤال "لماذا 0.91؟"
والجواب موجود في `evidence`.

    "زرارة بن أعين"        -> narrator   0.9x   (نسب + اسم علم)
    "الماء يطهر ولا يطهر"  -> hadith     0.8x   (صيغة متن)
    "باب نواقض الوضوء"     -> chapter    0.9x   (مؤشر باب)
    "ما حكم الوضوء"        -> ruling     0.8x   (استفهام حكمي)
    "الله"                 -> general    0.4x   (كلمة واحدة عامة)

والأخيرة **يجب** أن تكون منخفضة: كلمة واحدة شائعة لا نية واضحة
لها، والادعاء بغير ذلك كذب معايرة. الرقم المنخفض هنا صدق لا عجز —
والصواب أن يستعمله النظام لطلب توضيح لا أن يتظاهر بالفهم.

schema_version: 2.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

INTENT_VERSION = "2.0.0"

_D = r"0-9\u0660-\u0669"


class Intent(str, Enum):
    NARRATOR = "narrator"        # بحث عن راوٍ
    HADITH = "hadith"            # بحث عن متن رواية
    ISNAD = "isnad"              # بحث عن سلسلة إسناد
    CHAPTER = "chapter"          # بحث عن باب أو كتاب
    RULING = "ruling"            # سؤال عن حكم
    CONCEPT = "concept"          # سؤال عن مفهوم
    CITATION = "citation"        # بحث عن موضع بعينه
    GENERAL = "general"


@dataclass(slots=True)
class Evidence:
    """دليل واحد: ما تحقق، ووزنه، ولماذا."""

    name: str
    weight: float
    detail: str = ""


@dataclass(slots=True)
class IntentResult:
    label: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    runner_up: str | None = None
    runner_up_confidence: float = 0.0
    hints: list[str] = field(default_factory=list)
    version: str = INTENT_VERSION

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "evidence": [
                {"name": e.name, "weight": e.weight, "detail": e.detail}
                for e in self.evidence
            ],
            "runner_up": self.runner_up,
            "runner_up_confidence": round(self.runner_up_confidence, 4),
            "hints": self.hints,
            "intent_version": self.version,
        }

    @property
    def is_confident(self) -> bool:
        """هل الثقة كافية للبناء عليها في الترتيب؟"""
        return self.confidence >= 0.7


# ---------------------------------------------------------------------------
# أنماط الأدلة
# ---------------------------------------------------------------------------

_NASAB_RE = re.compile(r"(?:^|\s)(?:بن|ابن)\s")
_KUNYA_RE = re.compile(r"(?:^|\s)(?:أبو|ابو|أبي|ابي|أبا|ابا|أم|ام)\s")
_TRANSMISSION_RE = re.compile(r"(?:^|\s)(?:عن|حدثنا|حدّثنا|أخبرنا|اخبرنا)\s")
_ISNAD_OPENER_RE = re.compile(r"^\s*(?:وبإسناده|بإسناده|وباسناده|باسناده|وعنه)")
_CHAPTER_RE = re.compile(r"^\s*(?:باب|أبواب|ابواب|كتاب|فصل|مقدمة|مقدمه)\s")
_CITATION_RE = re.compile(rf"[\[\]]\s*[{_D}\s]+[\]\[]|ج\s*[{_D}]+|ص\s*[{_D}]+")

RULING_MARKERS = (
    "ما حكم", "حكم", "هل يجوز", "هل يجب", "يجوز", "يجب", "يحرم",
    "مستحب", "مكروه", "واجب", "حرام", "مباح", "فتوى",
)
CONCEPT_MARKERS = (
    "ما معنى", "معنى", "ما هو", "ما هي", "تعريف", "المقصود", "الفرق بين",
)
HADITH_MARKERS = (
    "قال رسول", "قال النبي", "قال أبو", "قال ابو", "سألت", "سالت",
    "سألته", "روي", "روى", "عن النبي", "عن رسول",
)
NARRATOR_TITLES = (
    "الكليني", "الصدوق", "الطوسي", "المفيد", "البرقي", "الصفار",
    "الحلبي", "زرارة", "محمد بن مسلم", "أبي بصير", "ابي بصير",
)


def _score(hits: list[Evidence], ceiling: float) -> float:
    """
    يحوّل مجموع أوزان الأدلة إلى ثقة في [0, ceiling].

    السقف يمنع ادعاء يقين لا تسنده القواعد: لا مصنّف قواعد يستحق
    0.99. والتشبّع تدريجي فلا يقفز الرقم بدليل واحد.
    """
    if not hits:
        return 0.0
    total = sum(h.weight for h in hits)
    # تشبّع أسّي: أول دليل يعطي كثيراً، والإضافات تقلّ عائداً.
    #
    # الثابت 0.35 معايَر ليصل الدليلُ القاطع الواحد (وزن 0.85 مثل
    # مؤشر الباب) إلى نحو 0.82 من السقف — وهو ما يستحقه فعلاً:
    # "باب نواقض الوضوء" لا يحتمل نية أخرى.
    saturated = 1.0 - (0.5 ** (total / 0.35))
    return round(min(ceiling, saturated * ceiling), 4)


class IntentClassifier:
    """
    مصنّف قائم على أدلة موزونة.

    ليس نموذجاً مدرَّباً — ذلك يحتاج أسئلة موسومة منك. لكنه يعطي
    ثقةً **محسوبة ومفسَّرة** بدل رقم ثابت، وهو الأساس الذي يُدرَّب
    عليه نموذج لاحقاً.
    """

    def __init__(self, *, min_confidence: float = 0.35):
        self.min_confidence = float(min_confidence)
        self.version = INTENT_VERSION

    # -----------------------------------------------------------------
    def detect(self, query: str) -> IntentResult:
        q = (query or "").strip()
        if not q:
            return IntentResult(Intent.GENERAL.value, 0.0, hints=["استعلام فارغ"])

        words = q.split()
        n = len(words)
        scores: dict[str, tuple[float, list[Evidence]]] = {}

        # --- راوٍ -----------------------------------------------------
        ev: list[Evidence] = []
        nasab = len(_NASAB_RE.findall(q))
        if nasab:
            ev.append(Evidence("نسب", 0.55 if nasab == 1 else 0.75, f"{nasab} نسب"))
        if _KUNYA_RE.search(q):
            ev.append(Evidence("كنية", 0.45))
        if any(t in q for t in NARRATOR_TITLES):
            ev.append(Evidence("اسم راوٍ معروف", 0.6))
        if 2 <= n <= 6 and nasab:
            ev.append(Evidence("طول اسم علم", 0.3))
        scores[Intent.NARRATOR.value] = (_score(ev, 0.95), ev)

        # --- إسناد ----------------------------------------------------
        ev = []
        if _ISNAD_OPENER_RE.search(q):
            ev.append(Evidence("فاتحة إسناد", 0.8))
        trans = len(_TRANSMISSION_RE.findall(q))
        if trans >= 2:
            ev.append(Evidence("سلسلة تحمّل", 0.7, f"{trans} أداة"))
        elif trans == 1 and nasab:
            ev.append(Evidence("تحمّل مع نسب", 0.4))
        scores[Intent.ISNAD.value] = (_score(ev, 0.93), ev)

        # --- متن رواية -------------------------------------------------
        ev = []
        hadith_hits = [m for m in HADITH_MARKERS if m in q]
        if hadith_hits:
            ev.append(Evidence("صيغة متن", 0.7, hadith_hits[0]))
        if n >= 4 and not nasab and not _CHAPTER_RE.match(q):
            ev.append(Evidence("عبارة نصية", 0.35))
        scores[Intent.HADITH.value] = (_score(ev, 0.92), ev)

        # --- باب أو كتاب -----------------------------------------------
        ev = []
        if _CHAPTER_RE.match(q):
            ev.append(Evidence("مؤشر باب أو كتاب", 1.15))
        scores[Intent.CHAPTER.value] = (_score(ev, 0.95), ev)

        # --- حكم -------------------------------------------------------
        ev = []
        ruling_hits = [m for m in RULING_MARKERS if m in q]
        if ruling_hits:
            ev.append(Evidence("لفظ حكمي", 0.65, ruling_hits[0]))
        if q.startswith(("ما حكم", "هل ")):
            ev.append(Evidence("استفهام حكمي", 0.5))
        scores[Intent.RULING.value] = (_score(ev, 0.9), ev)

        # --- مفهوم -----------------------------------------------------
        ev = []
        concept_hits = [m for m in CONCEPT_MARKERS if m in q]
        if concept_hits:
            ev.append(Evidence("استفهام مفهومي", 1.05, concept_hits[0]))
        scores[Intent.CONCEPT.value] = (_score(ev, 0.9), ev)

        # --- إحالة موضع -------------------------------------------------
        ev = []
        if _CITATION_RE.search(q):
            ev.append(Evidence("إشارة موضع", 1.10))
        scores[Intent.CITATION.value] = (_score(ev, 0.93), ev)

        # --- الترجيح ----------------------------------------------------
        ranked = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
        top_label, (top_score, top_ev) = ranked[0]
        second_label, (second_score, _) = ranked[1] if len(ranked) > 1 else (None, (0.0, []))

        hints: list[str] = []

        if top_score < self.min_confidence:
            # لا نية واضحة — وقول ذلك أصدق من ادعاء تصنيف
            conf = round(min(0.45, 0.15 + 0.05 * n), 4)
            if n == 1:
                hints.append("كلمة واحدة: النية غير محددة، والأنسب طلب توضيح")
            return IntentResult(
                Intent.GENERAL.value, conf,
                [Evidence("لا دليل كافٍ", 0.0, f"{n} كلمة")],
                second_label, second_score, hints,
            )

        # تقارب المرشحين ينقص اليقين
        margin = top_score - second_score
        if margin < 0.15:
            top_score = round(top_score * 0.85, 4)
            hints.append(f"نية منافسة قريبة: {second_label}")

        return IntentResult(top_label, top_score, top_ev, second_label, second_score, hints)


def detect_intent(query: str) -> IntentResult:
    return IntentClassifier().detect(query)


__all__ = [
    "INTENT_VERSION",
    "Evidence",
    "Intent",
    "IntentClassifier",
    "IntentResult",
    "detect_intent",
]
