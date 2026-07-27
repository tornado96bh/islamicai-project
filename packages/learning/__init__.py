"""
packages.learning — استيراد كسول.

كان هذا الملف يستورد LearningTrainer تلقائياً، وهو يسحب SessionLocal
الذي كان يبني محرك قاعدة البيانات عند الاستيراد. فصار استيراد أي
دالة تطبيع بسيطة يتطلب مشغّل PostgreSQL، وانهار جمع الاختبارات.

الأدوات الخفيفة تُستورد مباشرة كما كانت. أما LearningTrainer فيُحمَّل
عند أول طلب عبر __getattr__ (PEP 562)، فيبقى `from packages.learning
import LearningTrainer` يعمل بلا تغيير في أي مستدعٍ.
"""

from __future__ import annotations

from typing import Any


def _lazy_import(name: str, module_path: str, package: str):
    """
    يحمّل عند الطلب مع **إظهار السبب الحقيقي** عند الفشل.

    بدون هذا يتحوّل أي خطأ داخل الوحدة (تبعية ناقصة مثلاً) إلى
    AttributeError مبهم، فيراه المستدعي كـ
        ImportError: cannot import name 'X'
    ولا يعرف أن العلّة في مكان آخر تماماً.
    """
    import importlib

    try:
        module = importlib.import_module(module_path, package)
    except Exception as exc:  # التبعية الناقصة تُعلن عن نفسها
        raise ImportError(
            f"تعذّر تحميل {package}{module_path} المطلوب لـ '{name}': "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    try:
        return getattr(module, name)
    except AttributeError as exc:
        raise ImportError(
            f"الوحدة {package}{module_path} لا تعرّف '{name}'"
        ) from exc

from .context import ContextEntry, ContextLearner
from .dictionary import (
    DictionaryEntry,
    DictionaryLearner,
    normalize_surface_text,
    search_form_text,
    tokenize_text,
)
from .embeddings import EmbeddingBuilder
from .entities import EntityCandidate, EntityLearner
from .phrases import PhraseEntry, PhraseLearner

_LAZY = {"LearningTrainer": ".trainer"}


def __getattr__(name: str) -> Any:
    """يحمّل الثقيل عند الطلب فقط (PEP 562)."""
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = _lazy_import(name, module_path, __name__)
    globals()[name] = value
    return value



def __dir__() -> list[str]:
    return sorted(set(__all__))


__all__ = [
    "ContextEntry", "ContextLearner", "DictionaryEntry", "DictionaryLearner",
    "EmbeddingBuilder", "EntityCandidate", "EntityLearner", "LearningTrainer",
    "PhraseEntry", "PhraseLearner", "normalize_surface_text",
    "search_form_text", "tokenize_text",
]
