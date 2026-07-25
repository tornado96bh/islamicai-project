"""
مُبقى للتوافق فقط.

كان هذا الملف يحوي مطبّعاً ثانياً مختلفاً عن
packages/learning/canonicalizer.py، فكان السكربت الذي يكتب القاعدة
يستخدم واحداً والبحث يستخدم الآخر — ومنه اختلاف النتائج.

المطبّع الوحيد الآن: packages/utils/arabic_canonicalizer.py
"""

from packages.utils.arabic_canonicalizer import (  # noqa: F401
    canonicalize,
    normalize_for_search,
    normalize_surface_text,
    search_form_text,
    tokenize_text,
)

__all__ = [
    "canonicalize",
    "normalize_for_search",
    "normalize_surface_text",
    "search_form_text",
    "tokenize_text",
]
