"""
محرك الحركات والهمزات والجذور.

المشكلة التي يحلّها
-------------------
النظام كان يبني صيغتين للنص: أصلاً مقدّساً وصيغةً بحثية **منزوعة
الحركات**. فذابت فروق جوهرية في الفهرس:

    عَلَم  و  عِلْم  و  عَلِمَ      -> جميعها "علم"
    زُرارة (الراوي) و زِرارة      -> جميعها "زراره"
    مسؤول و مسئول                -> مختلفتان بلا داعٍ

فلا يستطيع الباحث أن يطلب الصيغة المشكولة بعينها، ولا أن يجمع
المتغيّرات الإملائية المتكافئة.

الطبقات الأربع
--------------
لكل نص أربع صيغ، لكل واحدة غرض لا تقوم غيرها مقامه:

    raw          الأصل. مقدّس. مرجع الاستشهاد العلمي.
    display      مقروء: بلا تمديد ولا تفكّك، **بكل الحركات والهمزات**.
    canonical    مشكول موحَّد: يحفظ الحركات ويوحّد الرسم فقط
                 (مسئول -> مسؤول). به يميَّز عَلَم من عِلْم.
    retrieval    بحثي: بلا حركات، بألف وهمزة موحّدتين.

والبحث يختار الطبقة بحسب صيغة السؤال:

    كتب المستخدم "علم"    -> retrieval  (يريد كل الاشتقاقات)
    كتب "عَلَم" بالحركات   -> canonical  (يريد هذه القراءة بعينها)

هذه هي القاعدة المركزية: **وجود الحركات في السؤال هو إعلان نية**.

schema_version: 1.0.0
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

DIACRITICS_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# محارف العربية
# ---------------------------------------------------------------------------

TATWEEL = "\u0640"

# الحركات: فتحة ضمة كسرة سكون شدة تنوين، والألف الخنجرية
HARAKAT = frozenset(
    "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0670\u0653\u0654\u0655"
)

# الهمزات بأشكالها
HAMZA_FORMS = {
    "\u0622": "\u0627",  # آ -> ا
    "\u0623": "\u0627",  # أ -> ا
    "\u0625": "\u0627",  # إ -> ا
    "\u0671": "\u0627",  # ٱ -> ا
}

# توحيد الرسم مع **حفظ** الحركات (طبقة canonical)
CANONICAL_MAP = {
    "\u0649": "\u064a",  # ى -> ي
    "\u0629": "\u0647",  # ة -> ه
    "\u0626": "\u0624",  # ئ -> ؤ  (مسئول = مسؤول)
    "\u06cc": "\u064a",  # ی الفارسية
    "\u06a9": "\u0643",  # ک الفارسية
}

_ARABIC_LETTER_RE = re.compile(r"[\u0621-\u064a]")
_WS_RE = re.compile(r"\s+")

# سوابق ولواحق تُقشَّر لاستخراج الجذع
_PREFIXES = ("وال", "بال", "كال", "فال", "ال", "لل", "و", "ف", "ب", "ك", "ل", "س")
_SUFFIXES = (
    "هما", "كما", "هم", "هن", "كم", "كن", "نا", "ها", "ية", "ات", "ون", "ين",
    "ان", "ته", "تي", "ه", "ك", "ي", "ا", "ت", "ن",
)


class TextLayer(str, Enum):
    """طبقات النص الأربع."""

    RAW = "raw"
    DISPLAY = "display"
    CANONICAL = "canonical"
    RETRIEVAL = "retrieval"


# ---------------------------------------------------------------------------
# التحويلات
# ---------------------------------------------------------------------------

def strip_tatweel(text: str) -> str:
    return (text or "").replace(TATWEEL, "")


def has_diacritics(text: str) -> bool:
    """
    هل في النص حركات؟

    هذا السؤال هو مفتاح اختيار طبقة البحث: من يكتب الحركات يقصدها.
    """
    return any(ch in HARAKAT for ch in (text or ""))


def diacritic_ratio(text: str) -> float:
    """نسبة الحروف المشكولة — تقدير لاكتمال التشكيل."""
    letters = _ARABIC_LETTER_RE.findall(text or "")
    if not letters:
        return 0.0
    marks = sum(1 for ch in (text or "") if ch in HARAKAT)
    return round(min(1.0, marks / len(letters)), 4)


def to_canonical(text: str) -> str:
    """
    توحيد الرسم **مع حفظ الحركات**.

    هذه الطبقة هي التي تميّز عَلَم من عِلْم، وتجمع مسئول مع مسؤول.
    لا تُحذف حركة واحدة هنا.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFC", strip_tatweel(text))
    out = "".join(CANONICAL_MAP.get(ch, ch) for ch in out)
    return _WS_RE.sub(" ", out).strip()


def to_retrieval(text: str) -> str:
    """
    الصيغة البحثية: بلا حركات، بألف وهمزة موحَّدتين.

    تُبنى من canonical لا من الخام، فيرث التوحيدَ الرسمي ثم تُنزع
    الحركات فوقه. الترتيب مقصود: لو نُزعت الحركات أولاً لضاعت
    معلومات تحتاجها بعض قواعد التوحيد.
    """
    base = to_canonical(text)
    out = []
    for ch in base:
        if ch in HARAKAT:
            continue
        out.append(HAMZA_FORMS.get(ch, ch))
    return _WS_RE.sub(" ", "".join(out)).strip()


def strip_diacritics(text: str) -> str:
    """ينزع الحركات وحدها دون أي توحيد آخر."""
    return "".join(ch for ch in (text or "") if ch not in HARAKAT)


# ---------------------------------------------------------------------------
# الجذع والجذر
# ---------------------------------------------------------------------------

def light_stem(word: str) -> str:
    """
    تقشير خفيف للسوابق واللواحق.

    ليس محللاً صرفياً كاملاً — ذلك يحتاج CAMeL Tools أو ما يماثله.
    لكنه يجمع "الوضوء" و"وضوء" و"بالوضوء" في جذع واحد، وهو ما يفيد
    البحث بالمفهوم دون خطر التحليل الخاطئ.
    """
    w = to_retrieval(word)
    if len(w) <= 3:
        return w

    # السوابق مرتّبة من الأطول للأقصر، وإلا قُشّرت "و" من "وال"
    # فبقيت "ال" ولم يتطابق "الوضوء" مع "وضوء".
    # حدّ البقاء أربعة أحرف لا ثلاثة: بثلاثة صارت "وضوء" -> "ضوء"
    # لأن الواو قُشّرت وهي أصلية. الأربعة تحمي الأصول الثلاثية
    # المزيدة، وتكلفتها أن بعض المشتقات لا تُقشَّر — وهذا أأمن.
    _MIN_KEEP = 4

    for prefix in sorted(_PREFIXES, key=len, reverse=True):
        if w.startswith(prefix) and len(w) - len(prefix) >= _MIN_KEEP:
            w = w[len(prefix) :]
            break

    for suffix in sorted(_SUFFIXES, key=len, reverse=True):
        if w.endswith(suffix) and len(w) - len(suffix) >= _MIN_KEEP:
            w = w[: -len(suffix)]
            break

    return w


@dataclass(slots=True)
class WordForms:
    """صيغ الكلمة الأربع، مع دليل التشكيل."""

    raw: str
    canonical: str
    retrieval: str
    stem: str
    is_diacritised: bool = False
    diacritic_ratio: float = 0.0

    def as_dict(self) -> dict:
        return {
            "raw": self.raw,
            "canonical": self.canonical,
            "retrieval": self.retrieval,
            "stem": self.stem,
            "is_diacritised": self.is_diacritised,
            "diacritic_ratio": self.diacritic_ratio,
        }


def analyse(word: str) -> WordForms:
    """يبني الصيغ الأربع لكلمة واحدة."""
    raw = word or ""
    return WordForms(
        raw=raw,
        canonical=to_canonical(raw),
        retrieval=to_retrieval(raw),
        stem=light_stem(raw),
        is_diacritised=has_diacritics(raw),
        diacritic_ratio=diacritic_ratio(raw),
    )


# ---------------------------------------------------------------------------
# المطابقة الواعية بالتشكيل
# ---------------------------------------------------------------------------

class MatchStrength(str, Enum):
    EXACT = "exact"              # مطابقة حرفية بالحركات
    CANONICAL = "canonical"      # مطابقة بعد توحيد الرسم، بالحركات
    UNVOCALISED = "unvocalised"  # مطابقة بعد نزع الحركات
    STEM = "stem"                # مطابقة الجذع
    NONE = "none"


# أوزان لكل درجة، لتدخل في الترتيب.
# المطابقة بالحركات أثمن حين يطلبها الباحث صراحةً.
MATCH_WEIGHTS = {
    MatchStrength.EXACT: 1.00,
    MatchStrength.CANONICAL: 0.92,
    MatchStrength.UNVOCALISED: 0.70,
    MatchStrength.STEM: 0.45,
    MatchStrength.NONE: 0.0,
}


@dataclass(slots=True)
class MatchResult:
    strength: MatchStrength
    weight: float
    reason: str = ""
    query_was_diacritised: bool = False


def match_words(query: str, target: str) -> MatchResult:
    """
    يقارن كلمتين ويرجّع **درجة** المطابقة لا نعم/لا.

    القاعدة الحاكمة: إن كتب الباحث الحركات فهو يقصدها، فالمطابقة
    غير المشكولة تنزل درجةً ولا تُقصى — لأن النص قد يكون غير مشكول
    في المصدر أصلاً.
    """
    q_raw, t_raw = (query or "").strip(), (target or "").strip()
    if not q_raw or not t_raw:
        return MatchResult(MatchStrength.NONE, 0.0, "أحدهما فارغ")

    q_diac = has_diacritics(q_raw)

    if q_raw == t_raw:
        return MatchResult(
            MatchStrength.EXACT, MATCH_WEIGHTS[MatchStrength.EXACT],
            "تطابق حرفي", q_diac,
        )

    q_can, t_can = to_canonical(q_raw), to_canonical(t_raw)
    if q_can == t_can:
        return MatchResult(
            MatchStrength.CANONICAL, MATCH_WEIGHTS[MatchStrength.CANONICAL],
            "تطابق بعد توحيد الرسم مع حفظ الحركات", q_diac,
        )

    q_ret, t_ret = to_retrieval(q_raw), to_retrieval(t_raw)
    if q_ret == t_ret:
        reason = (
            "تطابق بعد نزع الحركات — الاستعلام مشكول والنص ليس كذلك"
            if q_diac
            else "تطابق غير مشكول"
        )
        return MatchResult(
            MatchStrength.UNVOCALISED, MATCH_WEIGHTS[MatchStrength.UNVOCALISED],
            reason, q_diac,
        )

    if light_stem(q_raw) == light_stem(t_raw) and len(light_stem(q_raw)) >= 3:
        return MatchResult(
            MatchStrength.STEM, MATCH_WEIGHTS[MatchStrength.STEM],
            "تطابق الجذع", q_diac,
        )

    return MatchResult(MatchStrength.NONE, 0.0, "لا تطابق", q_diac)


@dataclass(slots=True)
class PhraseMatch:
    """نتيجة مطابقة عبارة كاملة."""

    score: float
    matched: int
    total: int
    strengths: list[str] = field(default_factory=list)
    diacritic_aware: bool = False

    @property
    def coverage(self) -> float:
        return round(self.matched / self.total, 4) if self.total else 0.0


def match_phrase(query: str, text: str) -> PhraseMatch:
    """
    يطابق عبارة على نص، ويرجّع درجةً مركّبة.

    كل كلمة من الاستعلام تُبحث عن أفضل مطابقة لها في النص، ثم
    يُجمع الوزن. فالعبارة المطابقة بالحركات تفوق المطابقة الخالية
    منها، دون أن تُقصيها.
    """
    q_words = [w for w in (query or "").split() if w]
    t_words = [w for w in (text or "").split() if w]
    if not q_words or not t_words:
        return PhraseMatch(0.0, 0, len(q_words))

    total_weight = 0.0
    matched = 0
    strengths: list[str] = []

    for qw in q_words:
        best = MatchResult(MatchStrength.NONE, 0.0)
        for tw in t_words:
            r = match_words(qw, tw)
            if r.weight > best.weight:
                best = r
            if best.strength is MatchStrength.EXACT:
                break
        if best.weight > 0:
            matched += 1
            total_weight += best.weight
            strengths.append(best.strength.value)

    return PhraseMatch(
        score=round(total_weight / len(q_words), 4),
        matched=matched,
        total=len(q_words),
        strengths=strengths,
        diacritic_aware=has_diacritics(query or ""),
    )


__all__ = [
    "CANONICAL_MAP",
    "DIACRITICS_VERSION",
    "HAMZA_FORMS",
    "HARAKAT",
    "MATCH_WEIGHTS",
    "MatchResult",
    "MatchStrength",
    "PhraseMatch",
    "TextLayer",
    "WordForms",
    "analyse",
    "diacritic_ratio",
    "has_diacritics",
    "light_stem",
    "match_phrase",
    "match_words",
    "strip_diacritics",
    "strip_tatweel",
    "to_canonical",
    "to_retrieval",
]
