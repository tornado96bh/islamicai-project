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

ENTITY_FILTER_VERSION = "1.0.0"


class EntityKind(str, Enum):
    PERSON = "person"
    BOOK = "book"
    PLACE = "place"
    ORGANIZATION = "organization"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


# حروف الجر وأدوات الربط — أي عبارة تبدأ بها ليست اسماً
LEADING_FUNCTION_WORDS = {
    # "علي" و"الي" ممنوعتان: التطبيع يوحّد "على" و"إلى" مع "علي" الاسم،
    # فإدراجهما يبتر "علي بن إبراهيم" إلى "بن إبراهيم".
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


# ألقاب مستقرة تُذكر مع صيغة الصلاة، وهي تسميات يبحث بها الباحث
_NASAB_IN_LABEL_RE = re.compile(r"(?:^|\s)(?:بن|ابن)\s")

SACRED_TITLE_PREFIXES = (
    "النبي", "الرسول", "رسول الله", "امير المومنين",
)

TRAILING_FUNCTION_WORDS = {
    "عن", "و", "ثم", "في", "من", "بن", "ابن", "،", "قال",
    "عنه", "عنها", "عنهم",
}


def _strip_trailing_function_words(tokens: list[str]) -> list[str]:
    """يزيل الأدوات من ذيل التسمية: "محمد بن يعقوب عن" -> "محمد بن يعقوب"."""
    out = list(tokens)
    while out and _norm(out[-1]) in TRAILING_FUNCTION_WORDS:
        out.pop()
    return out


def _strip_leading_function_words(tokens: list[str]) -> list[str]:
    """يزيل "عن" من "عن أحمد بن محمد" فيصير الكيان اسماً نظيفاً."""
    out = list(tokens)
    while out and _norm(out[0]) in LEADING_FUNCTION_WORDS:
        out.pop(0)
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

    # علامات الترقيم ليست جزءاً من اسم شخص.
    #
    # "النبي ) صلي الله عليه" كان يُقبل لأن الفحص كان على الألقاب
    # وحدها، فيدخل القوس وصيغة الصلاة في التسمية.
    if any(ch in raw for ch in "()[]{}«»؛؟!*"):
        return EntityVerdict(
            raw, EntityKind.REJECTED, False, "يحوي علامات ترقيم لا تكون في اسم"
        )

    # صيغة الصلاة لاحقة لا جزء من الاسم — إلا في ألقاب المعصومين
    # المستقرة، فـ"النبي صلى الله عليه وآله" تسمية مشروعة يستعملها
    # الباحث، بخلاف "أحمد بن محمد صلى الله عليه" التي تخلط راوياً
    # بلاحقة ليست منه.
    _n = _norm(raw)
    if any(f in _n for f in ("صلي الله", "صلى الله", "رضي الله")):
        # اللقب المشروع يبدأ بمؤشر معصوم **ولا يحوي نسباً**؛ فوجود
        # "بن" يعني أننا أمام راوٍ التصقت به الصيغة، لا لقباً.
        is_sacred_title = any(
            _n.startswith(t) for t in SACRED_TITLE_PREFIXES
        ) and not _NASAB_IN_LABEL_RE.search(_n)
        if not is_sacred_title:
            return EntityVerdict(
                raw, EntityKind.REJECTED, False, "صيغة صلاة ملتصقة باسم راوٍ"
            )

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
