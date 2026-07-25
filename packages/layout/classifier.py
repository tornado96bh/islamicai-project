"""
Layout Engine — تصنيف عناصر الصفحة.

لماذا هذا المحرك هو حجر الزاوية
-------------------------------
كل عنصر في قاعدتك الآن element_type="text" بلا استثناء. الأثر ليس
تجميلياً:

  * الكيانات المزعجة عندك ("من الباب"، "في الحديث") كلها مستخرجة من
    **الهوامش** — أمثلتها تبدأ بـ ")١ (" — لكن لا شيء يميّز الهامش
    عن المتن فتُعامل سواء.
  * لا يمكن استخراج سند بلا معرفة أين ينتهي السند ويبدأ المتن.
  * لا يمكن ملء عقد Hadith أو Isnad.
  * الترتيب لا يستطيع ترجيح المتن على الترويسة الجارية.

المنهج
------
تصنيف قائم على قواعد مستخرجة من أنماط متنك أنت، لا نموذج مدرَّب.
السبب: لا توجد بيانات موسومة بعد. هذا المحرك يُنتج الوسم الأولي
الذي تراجعه، ثم يصير أساساً لنموذج لاحقاً.

كل قرار يحمل confidence وسبباً. ما دون العتبة يبقى UNKNOWN بدل
التخمين — الوسم الخاطئ أضر من غيابه.

schema_version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

LAYOUT_VERSION = "1.1.0"


class LayoutType(str, Enum):
    MATN = "matn"                  # المتن
    SANAD = "sanad"                # السند
    HASHIYA = "hashiya"            # الحاشية
    FOOTNOTE = "footnote"          # الهامش
    TAKHRIJ = "takhrij"            # التخريج: ورواه فلان ... مثله
    HEADING = "heading"            # عنوان باب
    RUNNING_HEAD = "running_head"  # ترويسة جارية
    HADITH_NUMBER = "hadith_number"
    PAGE_NUMBER = "page_number"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# أنماط مستخرجة من متنك
# ---------------------------------------------------------------------------

_AR_DIGITS = r"\u0660-\u0669"
_DIGITS = rf"0-9{_AR_DIGITS}"

# ")١ (" أو "(١)" أو ")٢ (" في أول السطر
FOOTNOTE_MARKER_RE = re.compile(
    rf"^\s*[\)\(]\s*[{_DIGITS}]+\s*[\)\(]"
)

# "] ٧٦٨ ١ [" أو "] ٨٢٤ [ ٧" — ترقيم الحديث
HADITH_NUMBER_RE = re.compile(
    rf"^\s*\]\s*[{_DIGITS}\s]+\[|^\s*\[\s*[{_DIGITS}\s]+\]"
)

# "٧١ ـ باب ..." عنوان باب مرقَّم
NUMBERED_BAB_RE = re.compile(
    rf"^\s*[{_DIGITS}]+\s*[ـ\-–]\s*(باب|أبواب|ابواب)"
)

# "٨٩٢ كتاب الطهارة أبواب ..." ترويسة جارية: رقم صفحة + عنوان الكتاب
RUNNING_HEAD_RE = re.compile(
    rf"^\s*[{_DIGITS}]+\s+(كتاب|أبواب|ابواب)\s"
)

PAGE_NUMBER_ONLY_RE = re.compile(rf"^\s*[{_DIGITS}]+\s*$")

# إحالة مصدر في الهامش بلا قوسين:
#   "٠١ ـ الزهد / ٢٧ : ٢٩١ ."      "٧ ـ الفقيه . ١١ / ٨ : ١"
#   "٣١ ـ التهذيب : ١ ١٢٢ / ٠٣٦"
# البنية: رقم ـ اسم قصير ثم أرقام مفصولة بـ / أو :
# قاعدة بنيوية لا قائمة أسماء، فتعمّ على كتب لم تُذكر.
SOURCE_CITATION_RE = re.compile(
    rf"^\s*[{_DIGITS}]+\s*[ـ\-–]\s*\S[^:/]{{0,28}}[:/]\s*[{_DIGITS}\s/:.،]+$"
)

# عنوان كتاب أو قسم: "كتاب المضاربة ." — قصير ويبدأ بـ كتاب/أبواب
SECTION_TITLE_RE = re.compile(r"^\s*(كتاب|أبواب|ابواب)\s+\S")

# عبارات بدء السند
SANAD_OPENERS = (
    "وبإسناده", "بإسناده", "وباسناده", "باسناده",
    "حدثنا", "حدّثنا", "أخبرنا", "اخبرنا", "أنبأنا",
    "وعنه", "وعن", "عنه",
    "محمد بن يعقوب", "محمّد بن يعقوب",
)

# عبارات التخريج: إحالة إلى مصدر آخر
TAKHRIJ_OPENERS = (
    "ورواه", "رواه", "وأورده", "اورده", "وتقدم", "تقدم",
    "ويأتي", "يأتي", "وأخرجه", "اخرجه",
)
TAKHRIJ_TAIL = ("مثله", "نحوه", "بمعناه", "باختلاف")

# عبارات المتن النبوي والإمامي
MATN_MARKERS = (
    "قال رسول", "قال النبي", "قال أبو", "قال ابو",
    "سألته", "سالته", "سألت", "سالت",
    "عليه السلام ( :", "وآله ( :", "واله ( :",
)

# إحالات الهامش الداخلية
FOOTNOTE_PHRASES = (
    "في المصدر", "في نسخة", "في نسخه", "من الباب", "من أبواب", "من ابواب",
    "الكافي", "التهذيب", "الفقيه", "الاستبصار",
)

# علامة النسب — كثافتها تدل على سند
_NASAB_RE = re.compile(r"(?:^|\s)(بن|ابن)\s")
# علامة التحمّل
_TRANSMISSION_RE = re.compile(r"(?:^|\s)عن\s")


@dataclass(slots=True)
class LayoutVerdict:
    """حكم على عنصر، مع سببه ودرجة الثقة."""

    layout_type: LayoutType
    confidence: float
    reasons: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.layout_type is not LayoutType.UNKNOWN


class LayoutClassifier:
    """
    مصنّف عناصر الصفحة.

    min_confidence: ما دونها يُترك UNKNOWN. ارفعها لتقليل الأخطاء
    على حساب التغطية، واخفضها للعكس. القياس على عيّنة موسومة منك
    هو ما يحدد القيمة الصحيحة، لا الحدس.
    """

    def __init__(self, *, min_confidence: float = 0.55):
        self.min_confidence = float(min_confidence)
        self.version = LAYOUT_VERSION

    # -----------------------------------------------------------------
    def classify(
        self,
        text: str | None,
        *,
        element_order: int = 0,
        elements_on_page: int = 0,
    ) -> LayoutVerdict:
        """
        element_order و elements_on_page اختياريان لكنهما يحسّنان الدقة:
        الهوامش تقع في أسفل الصفحة، والترويسة في أعلاها.
        """
        raw = (text or "").strip()
        if not raw:
            return LayoutVerdict(LayoutType.UNKNOWN, 0.0, ["فارغ"])

        norm = self._normalize(raw)
        reasons: list[str] = []

        # --- 1) أنماط بنيوية قاطعة ---------------------------------
        if PAGE_NUMBER_ONLY_RE.match(raw):
            return LayoutVerdict(LayoutType.PAGE_NUMBER, 0.95, ["رقم مفرد"])

        if RUNNING_HEAD_RE.match(raw):
            return LayoutVerdict(
                LayoutType.RUNNING_HEAD, 0.90, ["رقم صفحة يليه عنوان الكتاب"]
            )

        if NUMBERED_BAB_RE.match(raw):
            return LayoutVerdict(LayoutType.HEADING, 0.92, ["باب مرقَّم"])

        if HADITH_NUMBER_RE.match(raw):
            # ترقيم الحديث يسبق السند مباشرة
            if self._looks_like_sanad(norm):
                return LayoutVerdict(
                    LayoutType.SANAD, 0.85, ["ترقيم حديث يليه سند"]
                )
            return LayoutVerdict(LayoutType.HADITH_NUMBER, 0.80, ["ترقيم حديث"])

        if FOOTNOTE_MARKER_RE.match(raw):
            return LayoutVerdict(LayoutType.FOOTNOTE, 0.93, ["يبدأ بعلامة هامش"])

        if SOURCE_CITATION_RE.match(raw):
            return LayoutVerdict(
                LayoutType.FOOTNOTE, 0.85, ["إحالة مصدر مرقَّمة (رقم ـ مصدر : أرقام)"]
            )

        # على النص المطبّع لا الخام: "ُكتاب" تبدأ بضمّة تكسر التطابق
        if SECTION_TITLE_RE.match(norm) and len(norm.split()) <= 6:
            return LayoutVerdict(LayoutType.HEADING, 0.80, ["عنوان كتاب أو أبواب"])

        # --- 2) الهامش بمحتواه لا بعلامته ---------------------------
        footnote_hits = [p for p in FOOTNOTE_PHRASES if p in norm]
        position_hint = (
            elements_on_page > 0 and element_order >= elements_on_page * 0.75
        )
        if footnote_hits:
            conf = 0.62 + 0.08 * min(len(footnote_hits), 3)
            if position_hint:
                conf += 0.10
                reasons.append("في أسفل الصفحة")
            reasons.append(f"عبارات إحالة: {', '.join(footnote_hits[:3])}")
            if conf >= self.min_confidence:
                return LayoutVerdict(LayoutType.FOOTNOTE, min(conf, 0.95), reasons)

        # --- 3) التخريج ---------------------------------------------
        starts_takhrij = any(norm.startswith(o) for o in TAKHRIJ_OPENERS)
        # "مثله )١( ." — نحذف إحالة الهامش الذيلية قبل فحص النهاية
        tail = re.sub(rf"[\)\(]\s*[{_DIGITS}]+\s*[\)\(]\s*[.،]?\s*$", "", norm)
        tail = tail.rstrip(" .،")
        ends_takhrij = any(tail.endswith(t) for t in TAKHRIJ_TAIL)
        if starts_takhrij or ends_takhrij:
            conf = 0.70 if (starts_takhrij and ends_takhrij) else 0.60
            reasons.append("صيغة تخريج")
            if conf >= self.min_confidence:
                return LayoutVerdict(LayoutType.TAKHRIJ, conf, reasons)

        # --- 4) السند ------------------------------------------------
        sanad_conf, sanad_reasons = self._sanad_score(norm)
        matn_conf, matn_reasons = self._matn_score(norm)

        if sanad_conf >= matn_conf and sanad_conf >= self.min_confidence:
            return LayoutVerdict(LayoutType.SANAD, sanad_conf, sanad_reasons)

        if matn_conf >= self.min_confidence:
            return LayoutVerdict(LayoutType.MATN, matn_conf, matn_reasons)

        return LayoutVerdict(
            LayoutType.UNKNOWN,
            max(sanad_conf, matn_conf),
            ["لا دليل كافٍ — تُرك بلا تصنيف عمداً"],
        )

    # -----------------------------------------------------------------
    def _looks_like_sanad(self, norm: str) -> bool:
        """
        هل يلي ترقيمَ الحديث سندٌ؟

        ترقيم الحديث "] ٧٦٨ ١ [" يسبق السند مباشرة في هذا المتن، لكن
        قد يسبق المتن أحياناً. نفحص ما بعده بدل الافتراض.
        """
        after = re.sub(r"^\s*[\]\[][^\]\[]*[\]\[]", "", norm).strip()
        if not after:
            return False
        if any(after.startswith(o) for o in SANAD_OPENERS):
            return True
        return (
            len(_NASAB_RE.findall(after)) >= 1
            and len(_TRANSMISSION_RE.findall(after)) >= 1
        )

    # -----------------------------------------------------------------
    def _sanad_score(self, norm: str) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0

        if any(norm.startswith(o) for o in SANAD_OPENERS):
            score += 0.45
            reasons.append("يبدأ بصيغة إسناد")
        else:
            # "محمد بن خالد ، عن ..." — الاسم المنسوب في المقدمة إسناد أيضاً
            head = norm.split()[:4]
            if "بن" in head or "ابن" in head:
                score += 0.28
                reasons.append("يبدأ باسم منسوب")

        nasab = len(_NASAB_RE.findall(norm))
        if nasab >= 2:
            score += 0.30
            reasons.append(f"{nasab} علامة نسب")
        elif nasab == 1:
            score += 0.12

        an_count = len(_TRANSMISSION_RE.findall(norm))
        if an_count >= 3:
            # ثلاث أدوات تحمّل فأكثر: سلسلة إسناد بلا شك تقريباً
            score += 0.45
            reasons.append(f"{an_count} أداة تحمّل (عن)")
        elif an_count == 2:
            score += 0.32
            reasons.append(f"{an_count} أداة تحمّل (عن)")
        elif an_count == 1:
            score += 0.10

        # "عن فلان بن فلان" — أداة تحمّل يليها اسم منسوب
        if re.search(r"عن\s+\S+\s+(بن|ابن)\s", norm):
            score += 0.18
            reasons.append("أداة تحمّل يليها اسم منسوب")

        # السند ينتهي عادة بـ "قال" التي تفتح المتن
        if norm.rstrip(" :.،").endswith("قال"):
            score += 0.10
            reasons.append("ينتهي بـ قال")

        return min(score, 0.95), reasons

    def _matn_score(self, norm: str) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0

        hits = [m for m in MATN_MARKERS if m in norm]
        if hits:
            score += 0.45 + 0.08 * min(len(hits), 3)
            reasons.append(f"صيغة متن: {hits[0]}")

        # المتن يغلب أن يكون جملة تامة بلا كثافة أنساب
        if len(norm.split()) >= 6 and len(_NASAB_RE.findall(norm)) == 0:
            score += 0.20
            reasons.append("جملة تامة بلا أنساب")

        if "؟" in norm or ":" in norm or "،" in norm:
            score += 0.05

        # النثر التام الخالي من أي علامة بنيوية هو المتن افتراضاً:
        # المحتوى الغالب على صفحة كتاب حديث هو المتن، لا الهوامش.
        digit_ratio = sum(
            1 for ch in norm if "\u0660" <= ch <= "\u0669" or ch.isdigit()
        ) / max(len(norm), 1)

        if (
            score < 0.55
            and len(norm.split()) >= 5
            and len(_NASAB_RE.findall(norm)) == 0
            and digit_ratio < 0.15  # كثافة الأرقام علامة إحالة لا متن
            and not any(norm.startswith(o) for o in TAKHRIJ_OPENERS)
            and not any(norm.startswith(o) for o in SANAD_OPENERS)
        ):
            score = max(score, 0.58)
            reasons.append("نثر تام بلا علامات بنيوية أخرى")

        return min(score, 0.95), reasons

    @staticmethod
    def _normalize(text: str) -> str:
        """تطبيع خفيف للمطابقة فقط — لا يمس المخرج."""
        out = []
        for ch in text:
            o = ord(ch)
            if 0x064B <= o <= 0x065F or o in (0x0670, 0x0640):
                continue
            if o in (0x0622, 0x0623, 0x0625, 0x0671):
                out.append("\u0627")
            elif o == 0x0649:
                out.append("\u064a")
            else:
                out.append(ch)
        return re.sub(r"\s+", " ", "".join(out)).strip()


# ---------------------------------------------------------------------------
# أوزان الترتيب المشتقة من التصنيف
# ---------------------------------------------------------------------------

# ترجيح المتن على الهامش في نتائج البحث. القيم في حجم أساس RRF
# (~0.02) حتى لا تبتلعه، اتساقاً مع درس الدفعة الثالثة.
LAYOUT_RANK_BONUS = {
    LayoutType.MATN: 0.012,
    LayoutType.SANAD: 0.006,
    LayoutType.HEADING: 0.004,
    LayoutType.TAKHRIJ: 0.000,
    LayoutType.HASHIYA: -0.004,
    LayoutType.FOOTNOTE: -0.008,
    LayoutType.RUNNING_HEAD: -0.012,
    LayoutType.HADITH_NUMBER: -0.010,
    LayoutType.PAGE_NUMBER: -0.015,
    LayoutType.UNKNOWN: 0.0,
}


def layout_bonus(layout_type: str | LayoutType | None) -> float:
    if layout_type is None:
        return 0.0
    try:
        key = LayoutType(layout_type) if isinstance(layout_type, str) else layout_type
    except ValueError:
        return 0.0
    return LAYOUT_RANK_BONUS.get(key, 0.0)


__all__ = [
    "LAYOUT_RANK_BONUS",
    "LAYOUT_VERSION",
    "LayoutClassifier",
    "LayoutType",
    "LayoutVerdict",
    "layout_bonus",
]
