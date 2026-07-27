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
    import importlib

    module = importlib.import_module(module_path, __name__)
    value = getattr(module, name)
    globals()[name] = value  # لا يُعاد التحميل
    return value


def __dir__() -> list[str]:
    return sorted(set(__all__))


__all__ = [
    "ContextEntry", "ContextLearner", "DictionaryEntry", "DictionaryLearner",
    "EmbeddingBuilder", "EntityCandidate", "EntityLearner", "LearningTrainer",
    "PhraseEntry", "PhraseLearner", "normalize_surface_text",
    "search_form_text", "tokenize_text",
]
