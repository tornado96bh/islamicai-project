"""
Entity Filter — تمييز الكيانات الحقيقية عن العبارات الشائعة.

المشكلة المرصودة في مخرجاتك:

    "من الباب"     kind=candidate   score=10.86   <- ليس كياناً
    "في الحديث"    kind=candidate   score=10.45   <- ليس كياناً
    "كتاب الطهارة" kind=candidate   score=10.30   <- عنوان، لا شخص
    "عن أحمد بن محمد"  kind=person   score=10.83  <- شخص، لكن "عن" زائدة

المستخرج الحالي يعتمد على التكرار وحده، والتكرار وحده لا يميّز الكيان
من العبارة الوظيفية: "من الباب" تكررت 6552 مرة لأنها صيغة إحالة، لا
لأنها اسم.

هذا الملف يضيف طبقة تصنيف قائمة على البنية اللغوية لا على التكرار.

schema_version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

ENTITY_FILTER_VERSION = "1.1.0"


class EntityKind(str, Enum):
    PERSON = "person"
    BOOK = "book"
    PLACE = "place"
    ORGANIZATION = "organization"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


# حروف الجر وأدوات الربط — أي عبارة تبدأ بها ليست اسماً
# "علي" و"الي" ممنوعتان هنا أيضاً: التطبيع يوحّد "على" و"إلى" مع
# "علي" الاسم، فإدراجها يبتر "علي بن إبراهيم" إلى "بن إبراهيم".
# وصيغ التحمّل في الأسانيد هي عن/حدثنا/أخبرنا لا "على"، فالخسارة معدومة.
LEADING_FUNCTION_WORDS = {
    "من", "في", "عن", "مع", "عند",
    "بعد", "قبل", "بين", "حتي", "حتى", "لدي", "لدى", "منذ", "خلال",
    "ثم", "او", "أو", "بل", "لكن", "و", "ف", "ب", "ل", "ك",
}

# كلمات إذا تكوّنت منها العبارة كلها فهي عبارة وظيفية لا كيان
GENERIC_NOUNS = {
    "الباب", "باب", "الحديث", "حديث", "الفصل", "فصل", "الجزء", "جزء",
    "المجلد", "مجلد", "الصفحة", "صفحه", "صفحة", "ابواب", "أبواب",
    "الكتاب", "كتاب", "المصدر", "نسخه", "نسخة", "مثله", "نحوه",
    "الاول", "الثاني", "الثالث", "الرابع", "الخامس",
}

# مؤشرات النسب — وجودها دليل قوي على اسم شخص
PERSON_MARKERS = {"بن", "ابن", "أبن", "ابو", "أبو", "ابي", "أبي", "ام", "أم", "بنت"}

# ألقاب تدل على شخص
PERSON_HONORIFICS = {
    "الشيخ", "الامام", "الإمام", "السيد", "العلامه", "العلامة",
    "الحافظ", "القاضي", "المولي", "المولى", "الحاج", "المحقق",
    "النبي", "رسول", "الرسول", "الصادق", "الباقر", "الكاظم", "الرضا",
    # هذه القوائم مقصود أن تُراجَع وتُوسَّع من متخصص — راجعها بنفسك
}

# مؤشرات عناوين الكتب
BOOK_MARKERS = {"كتاب", "رساله", "رسالة", "شرح", "تفسير", "مختصر", "تهذيب", "وسائل"}

_DIGIT_RE = re.compile(r"[0-9\u0660-\u0669\u06f0-\u06f9]")


@dataclass(slots=True)
class EntityVerdict:
    """حكم على مرشّح كيان، مع سببه (الماستر §9: كل قرار مفسَّر)."""

    label: str
    kind: EntityKind
    accepted: bool
    reason: str
    cleaned_label: str = ""

    def __bool__(self) -> bool:
        return self.accepted


def _tokens(label: str) -> list[str]:
    return [t for t in (label or "").split() if t]


# لواحق لا تكون آخر اسم: "محمد بن يعقوب عن" -> "محمد بن يعقوب"
# ملاحظة حاسمة: "علي" و"الي" ممنوعتان من هذه القائمة.
# التطبيع يوحّد "على" (حرف الجر) مع "علي" (الاسم)، و"إلى" مع "علي"،
# وعليّ من أشهر أسماء الرواة. إدراجها يبتر "محمد بن علي بن" إلى
# "محمد" وحدها. الأمان هنا أولى من التنظيف.
TRAILING_FUNCTION_WORDS = {
    "عن", "و", "ثم", "في", "من", "بن", "ابن", "،", "قال",
    "عنه", "عنها", "عنهم",
}


def _strip_leading_function_words(tokens: list[str]) -> list[str]:
    """يزيل "عن" من "عن أحمد بن محمد" فيصير الكيان اسماً نظيفاً."""
    out = list(tokens)
    while out and _norm(out[0]) in LEADING_FUNCTION_WORDS:
        out.pop(0)
    return out


def _strip_trailing_function_words(tokens: list[str]) -> list[str]:
    """
    يزيل الأدوات من ذيل التسمية.

    الكيانات المستخرجة من الأسانيد تلتقط أداة التحمّل التالية:
        "محم د بن يعقوب عن"   ->  "محم د بن يعقوب"
        "الحسين بن سعيد عن"   ->  "الحسين بن سعيد"
    و"بن" المعلّقة في الآخر تعني اسماً مبتوراً:
        "محم د بن علي بن"     ->  "محم د بن علي"
    """
    out = list(tokens)
    while out and _norm(out[-1]) in TRAILING_FUNCTION_WORDS:
        out.pop()
    return out


def _norm(token: str) -> str:
    """تطبيع خفيف للمقارنة فقط — لا يمس المخرج."""
    out = []
    for ch in token:
        o = ord(ch)
        if 0x064B <= o <= 0x065F or o == 0x0670 or o == 0x0640:
            continue
        if o in (0x0622, 0x0623, 0x0625, 0x0671):
            out.append("\u0627")
        elif o == 0x0649:
            out.append("\u064a")
        elif o == 0x0629:
            out.append("\u0647")
        else:
            out.append(ch)
    return "".join(out)


def classify_entity(label: str, *, min_tokens: int = 1) -> EntityVerdict:
    """
    يصنّف مرشّح كيان ويقرر قبوله أو رفضه.

    الترتيب مقصود: الرفض القاطع أولاً، ثم القبول بدليل بنيوي.
    """
    raw = (label or "").strip()
    if not raw:
        return EntityVerdict(raw, EntityKind.REJECTED, False, "فارغ")

    toks = _tokens(raw)
    normed = [_norm(t) for t in toks]

    # --- رفض قاطع -------------------------------------------------
    if _DIGIT_RE.search(raw):
        return EntityVerdict(raw, EntityKind.REJECTED, False, "يحتوي أرقاماً")

    if len(toks) > 6:
        return EntityVerdict(raw, EntityKind.REJECTED, False, "أطول من كيان")

    # العبارة المكوّنة كلها من كلمات وظيفية وأسماء عامة
    if all(t in LEADING_FUNCTION_WORDS or t in GENERIC_NOUNS for t in normed):
        return EntityVerdict(
            raw, EntityKind.REJECTED, False,
            "عبارة وظيفية بالكامل (مثل: من الباب / في الحديث)"
        )

    # --- تنظيف السوابق -------------------------------------------
    core = _strip_trailing_function_words(_strip_leading_function_words(toks))
    # نسب معلّق في المقدمة بعد التنظيف يعني اسماً مبتوراً
    while core and _norm(core[0]) in {"بن", "ابن"}:
        core.pop(0)
    core_norm = [_norm(t) for t in core]
    cleaned = " ".join(core)

    if not core:
        return EntityVerdict(raw, EntityKind.REJECTED, False, "لا يبقى شيء بعد حذف السوابق")

    if len(core) < min_tokens:
        return EntityVerdict(raw, EntityKind.REJECTED, False, "أقصر من الحد الأدنى")

    # بعد التنظيف، إن بقيت كلها عامة فهي ليست كياناً
    if all(t in GENERIC_NOUNS for t in core_norm):
        return EntityVerdict(raw, EntityKind.REJECTED, False, "أسماء عامة فقط")

    # --- قبول بدليل بنيوي ----------------------------------------
    # يبدأ باسم عام ليس مؤشر عنوان: إحالة قسم لا كيان
    #   "من أبواب أحكام المساكن" -> "أبواب أحكام" ليست كياناً
    # قاعدة بنيوية لا قائمة، فلا تحتاج ملاحقة كل تركيب على حدة.
    if core_norm and core_norm[0] in GENERIC_NOUNS and core_norm[0] not in BOOK_MARKERS:
        return EntityVerdict(
            raw, EntityKind.REJECTED, False, "يبدأ باسم عام (إحالة قسم لا كيان)"
        )

    if any(t in PERSON_MARKERS for t in core_norm):
        return EntityVerdict(raw, EntityKind.PERSON, True,
                             "يحوي نسباً (بن/ابن/أبو)", cleaned)

    if any(t in PERSON_HONORIFICS for t in core_norm):
        return EntityVerdict(raw, EntityKind.PERSON, True, "يحوي لقباً", cleaned)

    if core_norm and core_norm[0] in BOOK_MARKERS:
        return EntityVerdict(raw, EntityKind.BOOK, True, "يبدأ بمؤشر عنوان", cleaned)

    # اسم مفرد أو ثنائي بلا مؤشر: مرشّح ضعيف، يُقبل بدرجة أدنى
    if 1 <= len(core) <= 3:
        return EntityVerdict(raw, EntityKind.UNKNOWN, True,
                             "اسم محتمل بلا مؤشر بنيوي", cleaned)

    return EntityVerdict(raw, EntityKind.REJECTED, False, "لا دليل على كونه كياناً")


def filter_entities(
    candidates: list[dict],
    *,
    label_key: str = "label",
    keep_unknown: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    يفرز قائمة مرشّحين إلى مقبول ومرفوض.

    يرجّع (accepted, rejected) — والمرفوض يُحتفظ به مع سببه للمراجعة
    البشرية بدل الحذف الصامت (الماستر §2: لا حذف صامت).
    """
    accepted: list[dict] = []
    rejected: list[dict] = []

    for item in candidates:
        verdict = classify_entity(item.get(label_key, ""))
        enriched = dict(item)
        enriched["entity_kind"] = verdict.kind.value
        enriched["filter_reason"] = verdict.reason
        if verdict.cleaned_label:
            enriched["cleaned_label"] = verdict.cleaned_label

        keep = verdict.accepted and (
            keep_unknown or verdict.kind is not EntityKind.UNKNOWN
        )
        (accepted if keep else rejected).append(enriched)

    return accepted, rejected


__all__ = [
    "ENTITY_FILTER_VERSION",
    "EntityKind",
    "EntityVerdict",
    "classify_entity",
    "filter_entities",
]
