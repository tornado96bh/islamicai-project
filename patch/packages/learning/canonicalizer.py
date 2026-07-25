"""
مُبقى للتوافق فقط — يعيد التصدير من المطبّع الموحّد.

النسخة السابقة هنا لم تكن توحّد الألف/الهمزة/الياء/التاء المربوطة،
فكان "إسماعيل" لا يطابق "اسماعيل". انظر:
    packages/utils/arabic_canonicalizer.py
"""

from packages.utils.arabic_canonicalizer import (  # noqa: F401
    CANONICALIZER_VERSION,
    CanonResult,
    canonicalize,
    canonicalize_phrase,
    normalize_surface_text,
    search_form_text,
    tokenize_text,
)


def is_ocr_noise(text: str | None) -> bool:
    """يُقدّر ما إذا كان النص ضجيج OCR (تطويل ومسافات فقط)."""
    s = normalize_surface_text(text)
    if not s:
        return True
    noise = sum(1 for ch in s if ch in {"\u0640", " "})
    return noise >= max(8, len(s) // 2)


__all__ = [
    "CANONICALIZER_VERSION",
    "CanonResult",
    "canonicalize",
    "canonicalize_phrase",
    "normalize_surface_text",
    "search_form_text",
    "tokenize_text",
    "is_ocr_noise",
]
