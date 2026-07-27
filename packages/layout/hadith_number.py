"""
منظّف رقم الرواية.

المشكلة من مخرجاتك
------------------
    "] ٠٢٦ [ ٦"     "] ٧٣١ [ ١"     "] ٨١١ ١ ["

ثلاث علل مجتمعة:
  1. الأرقام هندية لم تُحوَّل، فلا تُقارَن ولا تُرتَّب
  2. الأقواس والمسافات باقية
  3. رقمان في حقل واحد بلا تمييز: رقم الرواية ورقم داخل الباب

وترتيب الرقمين ينعكس أحياناً ("] ٨١١ ١ [") لأن استخراج OCR يقلب
اتجاه النص. فالأكبر هو رقم الرواية عادةً، والأصغر ترتيبها في الباب.

schema_version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HADITH_NUMBER_VERSION = "1.0.0"

_ARABIC_INDIC = {ord("\u0660") + i: str(i) for i in range(10)}
_EXTENDED_INDIC = {ord("\u06f0") + i: str(i) for i in range(10)}
_DIGIT_RUN_RE = re.compile(r"\d+")


def to_western_digits(text: str) -> str:
    """يحوّل الأرقام الهندية والفارسية إلى غربية."""
    return (text or "").translate({**_ARABIC_INDIC, **_EXTENDED_INDIC})


@dataclass(slots=True)
class HadithNumber:
    raw: str
    hadith: int | None = None
    sequence: int | None = None   # الترتيب داخل الباب
    normalized: str = ""
    confidence: float = 0.0
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "raw": self.raw,
            "hadith": self.hadith,
            "sequence": self.sequence,
            "normalized": self.normalized,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
        }


def parse_hadith_number(raw: str | None) -> HadithNumber:
    """
    يفكّك حقل الرقم الخام.

    لا يُخترع رقم عند الغموض: تُرجَّع ثقة منخفضة وسببها، فيبقى
    القرار للمراجعة البشرية.
    """
    text = (raw or "").strip()
    if not text:
        return HadithNumber(raw="", reason="فارغ")

    western = to_western_digits(text)
    runs = [int(m) for m in _DIGIT_RUN_RE.findall(western)]

    if not runs:
        return HadithNumber(text, reason="لا أرقام")

    if len(runs) == 1:
        n = runs[0]
        return HadithNumber(
            text, hadith=n, normalized=f"[{n}]", confidence=0.85,
            reason="رقم واحد",
        )

    # رقمان: الأكبر رقم الرواية، والأصغر ترتيبها في الباب.
    # الاعتماد على القيمة لا على الموضع، لأن ترتيب النص قد ينعكس.
    ordered = sorted(runs, reverse=True)
    hadith, sequence = ordered[0], ordered[1]

    # حراسة: رقمان متقاربان جداً يعني أن أحدهما ليس ترتيباً
    confidence = 0.9 if hadith > sequence * 3 else 0.6
    reason = (
        "الأكبر رقم رواية والأصغر ترتيب في الباب"
        if confidence >= 0.9
        else "رقمان متقاربان — التمييز غير مؤكد"
    )

    return HadithNumber(
        text, hadith=hadith, sequence=sequence,
        normalized=f"[{hadith}] {sequence}", confidence=confidence, reason=reason,
    )


__all__ = ["HADITH_NUMBER_VERSION", "HadithNumber", "parse_hadith_number",
           "to_western_digits"]
