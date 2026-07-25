"""
Arabic canonicalizer — IslamicAI

المطبّع العربي الموحّد. يحل ثلاث مشاكل في النسخة القديمة:

1. النسخة القديمة لم تكن توحّد الألف/الهمزة/الياء/التاء المربوطة،
   فكان "إسماعيل" لا يطابق "اسماعيل".
2. لم تكن تغطي علامات المدّ والهمزة (0653-0655) ولا العلامات القرآنية
   (06D6-06ED, 08D3-08FF).
3. الأهم: التطبيع يغيّر أطوال السلاسل، فينكسر الربط بين النص المسترجَع
   وموضعه الأصلي في الصفحة (bounding box). هذا الملف يحل ذلك بإرجاع
   خريطة إزاحة ثنائية الاتجاه.

قاعدة الاستخدام:
    - الفهرسة والبحث  -> على canonical
    - العرض والاستشهاد -> من raw عبر خريطة الإزاحة

schema_version: 1.0.0
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

CANONICALIZER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# مجموعات المحارف
# ---------------------------------------------------------------------------

# محارف تُحذف بالكامل (لا تنتج أي مخرج)
_ZERO_WIDTH = {
    "\u200b",  # ZERO WIDTH SPACE
    "\u200c",  # ZWNJ
    "\u200d",  # ZWJ
    "\u200e",  # LRM
    "\u200f",  # RLM
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # bidi embedding
    "\u2066", "\u2067", "\u2068", "\u2069",            # bidi isolates
    "\ufeff",  # BOM
    "\u00ad",  # SOFT HYPHEN
}

_TATWEEL = "\u0640"


def _is_arabic_mark(ch: str) -> bool:
    """
    علامات تُحذف في الصيغة البحثية: التشكيل، الهمزات العائمة، المدّ،
    وعلامات الضبط القرآني.

    ملاحظة: 0670 (الألف الخنجرية) تُحذف أيضاً، لأن "الرحمن" تُكتب بها
    وبدونها في طبعات مختلفة.
    """
    o = ord(ch)
    return (
        0x064B <= o <= 0x065F   # التشكيل + الهمزات العائمة + المدّ
        or o == 0x0670          # ألف خنجرية
        or 0x06D6 <= o <= 0x06ED  # علامات الوقف والضبط القرآني
        or 0x08D3 <= o <= 0x08FF  # علامات قرآنية ممتدة
        or o == 0x061A
    )


# استبدالات محرف-بمحرف (طول ثابت = خريطة الإزاحة تبقى دقيقة)
_LETTER_FOLD = {
    # الألف بكل صورها
    "\u0622": "\u0627",  # آ
    "\u0623": "\u0627",  # أ
    "\u0625": "\u0627",  # إ
    "\u0671": "\u0627",  # ٱ ألف وصل
    "\u0672": "\u0627",
    "\u0673": "\u0627",
    "\u0675": "\u0627",
    # الياء والألف المقصورة
    "\u0649": "\u064a",  # ى -> ي
    "\u06cc": "\u064a",  # ی فارسية
    "\u064a": "\u064a",
    # التاء المربوطة
    "\u0629": "\u0647",  # ة -> ه
    # الهمزات على كرسي
    "\u0624": "\u0648",  # ؤ -> و
    "\u0626": "\u064a",  # ئ -> ي
    "\u0621": "",        # ء مفردة تُحذف في الصيغة البحثية
    # حروف فارسية/أردية شائعة في المخطوطات
    "\u06a9": "\u0643",  # ک -> ك
    "\u06af": "\u0643",  # گ -> ك
    "\u067e": "\u0628",  # پ -> ب
    "\u0686": "\u062c",  # چ -> ج
    "\u0698": "\u0632",  # ژ -> ز
    "\u06be": "\u0647",  # ھ -> ه
    "\u06c0": "\u0647",
    "\u06d5": "\u0647",
    # الأرقام العربية-الهندية -> لاتينية
    "\u0660": "0", "\u0661": "1", "\u0662": "2", "\u0663": "3", "\u0664": "4",
    "\u0665": "5", "\u0666": "6", "\u0667": "7", "\u0668": "8", "\u0669": "9",
    "\u06f0": "0", "\u06f1": "1", "\u06f2": "2", "\u06f3": "3", "\u06f4": "4",
    "\u06f5": "5", "\u06f6": "6", "\u06f7": "7", "\u06f8": "8", "\u06f9": "9",
}

# تصحيحات OCR شائعة (تُطبَّق على مستوى الكلمة، بعد التطبيع)
OCR_WORD_FIXES = {
    "االله": "الله",
    "االلة": "الله",
    "اللة": "الله",
    "هللا": "الله",
}


# ---------------------------------------------------------------------------
# النتيجة
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CanonResult:
    """نتيجة التطبيع مع خريطة الإزاحة."""

    raw: str
    canonical: str
    # offsets[i] = فهرس المحرف في raw الذي أنتج canonical[i]
    offsets: list[int] = field(default_factory=list)
    version: str = CANONICALIZER_VERSION

    def to_raw_span(self, start: int, end: int) -> tuple[int, int]:
        """
        يحوّل مدى في النص المُطبَّع إلى مدى مقابل في النص الأصلي.
        هذه هي الدالة التي تحفظ ربط نتيجة البحث بموضعها على الصفحة.
        """
        if not self.offsets or start >= end:
            return (0, 0)
        start = max(0, min(start, len(self.offsets) - 1))
        end = max(start + 1, min(end, len(self.offsets)))
        raw_start = self.offsets[start]
        raw_end = self.offsets[end - 1] + 1
        return (raw_start, raw_end)

    def raw_excerpt(self, start: int, end: int) -> str:
        """يستخرج المقطع الأصلي (بتشكيله وهمزاته) المقابل لمدى مُطبَّع."""
        a, b = self.to_raw_span(start, end)
        return self.raw[a:b]


# ---------------------------------------------------------------------------
# النواة
# ---------------------------------------------------------------------------

def canonicalize(text: str | None, *, fold_letters: bool = True) -> CanonResult:
    """
    يطبّع النص ويبني خريطة الإزاحة في مرور واحد.

    fold_letters=True  -> الصيغة البحثية (توحيد الألف/الياء/التاء + حذف التشكيل)
    fold_letters=False -> الصيغة السطحية (تنظيف فقط، مع إبقاء التشكيل)
    """
    raw = text or ""
    out_chars: list[str] = []
    out_offsets: list[int] = []

    pending_space_src: int | None = None

    for i, ch in enumerate(raw):
        # 1) محارف تُحذف دائماً
        if ch in _ZERO_WIDTH or ch == _TATWEEL:
            continue

        # 2) المسافات: تُطوى إلى مسافة واحدة
        if ch.isspace():
            if out_chars:
                pending_space_src = i
            continue

        # 3) التشكيل والعلامات
        if fold_letters and _is_arabic_mark(ch):
            continue

        # 4) تطبيع Unicode على مستوى المحرف (يفكّ صور العرض والروابط)
        #    per-char NFKC حتى تبقى الخريطة دقيقة: كل مخرج يُنسب إلى i
        expanded = unicodedata.normalize("NFKC", ch)

        # 5) الطيّ الحرفي
        pieces: list[str] = []
        for sub in expanded:
            if fold_letters and _is_arabic_mark(sub):
                continue
            if fold_letters:
                sub = _LETTER_FOLD.get(sub, sub)
            if sub:
                pieces.append(sub)

        if not pieces:
            continue

        # نضيف المسافة المعلّقة فقط إذا سيأتي بعدها محتوى فعلي
        if pending_space_src is not None:
            out_chars.append(" ")
            out_offsets.append(pending_space_src)
            pending_space_src = None

        for sub in pieces:
            out_chars.append(sub)
            out_offsets.append(i)

    canonical = "".join(out_chars)

    # 6) تصحيحات OCR على مستوى الكلمة (تحافظ على الخريطة لأنها
    #    تُطبَّق فقط حين يتساوى الطول أو يقصر، ونعيد بناء الخريطة بأمان)
    if fold_letters and canonical:
        canonical, out_offsets = _apply_word_fixes(canonical, out_offsets)

    return CanonResult(raw=raw, canonical=canonical, offsets=out_offsets)


def _apply_word_fixes(text: str, offsets: list[int]) -> tuple[str, list[int]]:
    """يطبّق تصحيحات OCR على مستوى الكلمة مع تحديث خريطة الإزاحة."""
    if not any(bad in text for bad in OCR_WORD_FIXES):
        return text, offsets

    out_chars: list[str] = []
    out_offsets: list[int] = []
    start = 0
    n = len(text)

    while start < n:
        end = text.find(" ", start)
        if end == -1:
            end = n
        word = text[start:end]
        fixed = OCR_WORD_FIXES.get(word)

        if fixed is not None:
            # كل محارف الكلمة المصححة تُنسب إلى أول محرف من الكلمة الأصلية
            anchor = offsets[start]
            for ch in fixed:
                out_chars.append(ch)
                out_offsets.append(anchor)
        else:
            for k in range(start, end):
                out_chars.append(text[k])
                out_offsets.append(offsets[k])

        if end < n:  # المسافة الفاصلة
            out_chars.append(" ")
            out_offsets.append(offsets[end])
        start = end + 1

    return "".join(out_chars), out_offsets


# ---------------------------------------------------------------------------
# واجهات متوافقة مع الكود القائم
# ---------------------------------------------------------------------------

def normalize_surface_text(text: str | None) -> str:
    """الصيغة السطحية: تنظيف بلا حذف تشكيل. تُحفظ في text_raw المعروض."""
    return canonicalize(text, fold_letters=False).canonical


def search_form_text(text: str | None) -> str:
    """الصيغة البحثية: هذه ما يُفهرَس ويُبحث فيه."""
    return canonicalize(text, fold_letters=True).canonical


def tokenize_text(text: str | None) -> list[str]:
    """تقطيع بسيط إلى كلمات على الصيغة البحثية."""
    form = search_form_text(text)
    return [t for t in form.split(" ") if t]


def canonicalize_phrase(text: str | None) -> str:
    return " ".join(tokenize_text(text))


# نفس التوقيع القديم في packages/utils/arabic_normalizer.py
def normalize_for_search(text: str | None) -> str:
    return search_form_text(text)


__all__ = [
    "CANONICALIZER_VERSION",
    "CanonResult",
    "canonicalize",
    "normalize_surface_text",
    "search_form_text",
    "tokenize_text",
    "canonicalize_phrase",
    "normalize_for_search",
]
