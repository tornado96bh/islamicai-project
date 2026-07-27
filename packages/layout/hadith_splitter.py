"""
Hadith Splitter — تقسيم الرواية إلى رقم وسند ومتن.

القالب الذي حدّدتَه
-------------------
    [ 29214 ] 1 ـ محمد بن يعقوب ، عن محمد بن يحيى ، عن أحمد بن محمد ،
    عن ابن محبوب ، عن أبي أيوب الخرّاز ، عن محمد بن مسلم ، قال :
    سألت أبا جعفر ( عليه السلام ) عن رجل دبر مملوكا له ، ثمّ احتاج
    إلى ثمنه ، فقال : هو مملوكه ...

    الرقم : [ 29214 ]
    السند : محمد بن يعقوب ... قال : سألت أبا جعفر ( عليه السلام )
    المتن : عن رجل دبر مملوكا له ، ثمّ احتاج إلى ثمنه ...

القاعدة الحاكمة
---------------
السند ينتهي **بعد لقب المعصوم** الذي يلي اسمه، لا عند أول "قال".
في مثالك ينتهي عند "( عليه السلام )" التالية لـ"أبا جعفر"، فيدخل
"قال : سألت أبا جعفر" في السند لأنه من كلام الراوي لا من المتن.

مبدأ صارم
---------
**لا يُحذف حرف ولا حركة ولا نقطة.** المقسّم يرجّع مواضع القطع
(offsets) في النص الأصلي، والأجزاء مقتطعة منه حرفياً. فيمكن دائماً
إعادة تركيب النص كاملاً من أجزائه.

schema_version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HADITH_SPLITTER_VERSION = "1.1.0"

_D = r"0-9\u0660-\u0669"

# "[ 29214 ]" أو "] 29214 [" (ينعكس ترتيبها في استخراج OCR)
NUMBER_RE = re.compile(rf"^\s*[\[\]]\s*[{_D}\s]+[\]\[]\s*(?:[{_D}]+\s*[ـ\-–]?\s*)?")

# ألقاب المعصومين — نهاية السند تقع بعد آخرها
HONORIFIC_RE = re.compile(
    r"[\(\)]\s*(?:"
    r"علي[هى]\s*ال?سلام"
    r"|عليهم\s*ال?سلام"
    r"|عليهما\s*ال?سلام"
    r"|صل[يى]\s*الل?ه\s*علي[هى]\s*و?[اآ]ل[هى]"
    r"|سلام\s*الله\s*علي"
    r")\s*[\)\(]"
)

# صيغ التحمّل
TRANSMISSION_RE = re.compile(r"(?:^|\s)عن\s")
NASAB_RE = re.compile(r"(?:^|\s)(?:بن|ابن)\s")

# فاتحة السند
SANAD_OPENERS = (
    "محمد بن يعقوب", "محمّد بن يعقوب", "محم د بن يعقوب",
    "وبإسناده", "بإسناده", "وباسناده", "باسناده",
    "حدثنا", "حدّثنا", "أخبرنا", "اخبرنا", "وعنه", "وعن", "عنه",
)

# ما يفتح المتن بعد السند حين لا يوجد لقب
MATN_OPENERS = ("قال :", "قال:", "فقال :", "قال ؟", "أنه قال", "انه قال")


@dataclass(slots=True)
class HadithParts:
    """أجزاء الرواية، مع مواضعها في النص الأصلي."""

    raw: str
    number: str = ""
    isnad: str = ""
    matn: str = ""
    number_span: tuple[int, int] = (0, 0)
    isnad_span: tuple[int, int] = (0, 0)
    matn_span: tuple[int, int] = (0, 0)
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def reassemble(self) -> str:
        """
        يعيد تركيب النص من أجزائه.

        يجب أن يطابق raw حرفاً بحرف — وهو ما يضمن ألا يضيع شيء.
        """
        return self.raw[self.number_span[0] : self.matn_span[1]] if self.matn else self.raw

    def is_complete(self) -> bool:
        return bool(self.isnad and self.matn)


class HadithSplitter:
    """
    مقسّم قائم على القواعد البنيوية للرواية.

    min_confidence: ما دونها يُرجَّع النص كاملاً بلا تقسيم، لأن
    التقسيم الخاطئ أضر من غيابه — قد ينسب كلام الراوي إلى المعصوم.
    """

    def __init__(self, *, min_confidence: float = 0.5):
        self.min_confidence = float(min_confidence)
        self.version = HADITH_SPLITTER_VERSION

    # -----------------------------------------------------------------
    def split(self, text: str | None) -> HadithParts:
        raw = text or ""
        if not raw.strip():
            return HadithParts(raw=raw, reasons=["فارغ"])

        parts = HadithParts(raw=raw)
        cursor = 0

        # 1) رقم الرواية
        m = NUMBER_RE.match(raw)
        if m:
            parts.number = raw[m.start() : m.end()].strip()
            parts.number_span = (m.start(), m.end())
            cursor = m.end()
            parts.reasons.append("رقم رواية في المقدمة")

        body_start = cursor
        body = raw[body_start:]
        if not body.strip():
            return parts

        # 2) هل هذا نصّ رواية أصلاً؟
        #
        # التقسيم كان يُطبَّق على كل نص فأنتج عبثاً:
        #     matn_text = ": قال"
        #     matn_text = ": يؤمر برج ال إلى النار"
        # وهي أجزاء جملة لا متونَ روايات. الشرط: إمّا سلسلة إسناد
        # ظاهرة، وإمّا رقم رواية في المقدمة.
        if not parts.number and not self._has_report_structure(body):
            parts.matn = body.strip()
            parts.matn_span = (body_start, len(raw))
            parts.confidence = 0.3
            parts.reasons.append("ليس نص رواية — لا تقسيم")
            return parts

        # 3) نهاية السند
        split_at, reason, conf = self._find_isnad_end(body)

        if split_at is None:
            # لا فاصل واضح: هل هو سند كامل بلا متن، أم متن بلا سند؟
            if self._looks_like_isnad(body):
                parts.isnad = body.strip()
                parts.isnad_span = (body_start, len(raw))
                parts.confidence = 0.55
                parts.reasons.append("سند بلا متن ظاهر")
            else:
                parts.matn = body.strip()
                parts.matn_span = (body_start, len(raw))
                parts.confidence = 0.5
                parts.reasons.append("متن بلا سند ظاهر")
            return parts

        isnad_text = body[:split_at].strip()
        matn_text = body[split_at:].strip()

        if not matn_text:
            parts.isnad = isnad_text
            parts.isnad_span = (body_start, len(raw))
            parts.confidence = 0.55
            parts.reasons.append("سند بلا متن بعد الفاصل")
            return parts

        # متن من كلمة أو كلمتين ليس متناً بل بقية جملة
        if len(matn_text.split()) < 3:
            parts.isnad = isnad_text
            parts.isnad_span = (body_start, len(raw))
            parts.confidence = 0.5
            parts.reasons.append("ما بعد الفاصل أقصر من متن")
            return parts

        parts.isnad = isnad_text
        parts.isnad_span = (body_start, body_start + split_at)
        parts.matn = matn_text
        parts.matn_span = (body_start + split_at, len(raw))
        parts.confidence = conf
        parts.reasons.append(reason)

        if parts.confidence < self.min_confidence:
            parts.reasons.append("ثقة دون العتبة — يُترك بلا تقسيم")
            return HadithParts(
                raw=raw,
                number=parts.number,
                number_span=parts.number_span,
                matn=raw[body_start:].strip(),
                matn_span=(body_start, len(raw)),
                confidence=parts.confidence,
                reasons=parts.reasons,
            )

        return parts

    # -----------------------------------------------------------------
    def _find_isnad_end(self, body: str) -> tuple[int | None, str, float]:
        """
        يحدد موضع نهاية السند.

        الأولوية للقب المعصوم: هو الفاصل الأدق لأن ما بعده كلام
        المعصوم أو سؤال السائل عن موضوع، وما قبله سلسلة الرواة.
        """
        # (أ) آخر لقب في النصف الأول
        limit = max(int(len(body) * 0.75), 40)
        last = None
        for m in HONORIFIC_RE.finditer(body):
            if m.start() < limit:
                last = m
        if last is not None:
            head = body[: last.end()]
            if TRANSMISSION_RE.search(head) or NASAB_RE.search(head):
                return last.end(), "ينتهي السند بعد لقب المعصوم", 0.85
            return last.end(), "لقب معصوم بلا سلسلة رواة قبله", 0.6

        # (ب) أول فاتحة متن بعد سلسلة إسناد
        for opener in MATN_OPENERS:
            idx = body.find(opener)
            if idx > 0:
                head = body[:idx]
                if len(TRANSMISSION_RE.findall(head)) >= 1 and NASAB_RE.search(head):
                    return idx + len(opener), f"فاتحة متن: {opener.strip()}", 0.7

        return None, "لا فاصل واضح", 0.0

    @staticmethod
    def _has_report_structure(body: str) -> bool:
        """
        هل في النص بنية رواية؟

        الشرط: سلسلة تحمّل (عن ... عن) مع نسب، أو فاتحة إسناد صريحة.
        المتن المجرد أو جزء الجملة لا يُقسَّم.
        """
        if any(body.lstrip().startswith(o) for o in SANAD_OPENERS):
            return True
        transmissions = len(TRANSMISSION_RE.findall(body))
        nasab = len(NASAB_RE.findall(body))
        return transmissions >= 2 and nasab >= 1

    @staticmethod
    def _looks_like_isnad(body: str) -> bool:
        if any(body.lstrip().startswith(o) for o in SANAD_OPENERS):
            return True
        return (
            len(TRANSMISSION_RE.findall(body)) >= 2
            and len(NASAB_RE.findall(body)) >= 1
        )


# ذيل اللقب يبقى ملتصقاً بالاسم بعد القطع على الفاصلة
_TRAILING_HONORIFIC_RE = re.compile(
    r"\s*[\(\)]?\s*(?:علي[هى]|عليهم|عليهما|صل[يى])\s+.*$"
)

# أسماء المعصومين وكناهم كما ترد في الأسانيد
IMAM_MARKERS = (
    "أبا جعفر", "ابا جعفر", "أبي جعفر", "ابي جعفر",
    "أبا عبد الله", "ابا عبد الله", "أبي عبد الله", "ابي عبد الله",
    "أبا الحسن", "ابا الحسن", "أبي الحسن", "ابي الحسن",
    "الرضا", "الصادق", "الباقر", "الكاظم", "أمير المؤمنين", "امير المومنين",
    "رسول الله", "النبي",
)


def identify_imam(isnad: str) -> str:
    """
    يفصل المعصوم المروي عنه عن سلسلة الرواة.

    المعصوم ليس حلقة في السند بل منتهاه، وخلطه بالرواة يفسد أي رسم
    بياني للإسناد لاحقاً.
    """
    text = isnad or ""
    for marker in IMAM_MARKERS:
        if marker in text:
            return marker
    return ""


def extract_narrators(isnad: str) -> list[str]:
    """
    يستخرج أسماء الرواة من السند بالترتيب.

    القطع على "عن" و"،" — وهو تقريب. الربط بكيانات الرواة (Narrator
    Resolution) يحتاج قائمة معتمدة منك، وهو خارج نطاق هذا المقسّم.
    """
    if not isnad:
        return []

    body = isnad
    for opener in SANAD_OPENERS:
        if body.lstrip().startswith(opener):
            break

    chunks = re.split(r"\s*،\s*|\s+عن\s+", body)
    out: list[str] = []
    for chunk in chunks:
        name = chunk.strip(" .،:؛()[]")
        # "، عن فلان" يُقطع على الفاصلة أولاً فتبقى "عن" بادئةً
        for particle in ("عن ", "وعن ", "عنه ", "قال : سألت ", "قال : سالت ",
                         "سألت ", "سالت "):
            if name.startswith(particle):
                name = name[len(particle):].strip()
                break
        if not name or len(name.split()) > 6:
            continue
        # نستبعد صيغ التحمّل والأفعال
        if name in {"قال", "حدثنا", "أخبرنا", "وبإسناده", "بإسناده", "عنه"}:
            continue
        name = _TRAILING_HONORIFIC_RE.sub("", name).strip(" .،:؛()[]")
        if not name or len(name) < 3:
            continue
        # المعصوم ليس حلقة في السلسلة
        if any(name.startswith(m) or name == m for m in IMAM_MARKERS):
            continue
        out.append(name)
    return out


__all__ = [
    "HADITH_SPLITTER_VERSION",
    "IMAM_MARKERS",
    "identify_imam",
    "HadithParts",
    "HadithSplitter",
    "extract_narrators",
]
