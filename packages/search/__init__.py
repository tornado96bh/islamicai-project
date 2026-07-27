"""
packages.search — استيراد كسول.

نفس علّة الحزم الأخرى: استيراد SearchEngine يسحب طبقة قاعدة البيانات
كاملة، فيصير اختبار دالة ترتيب خالصة متوقفاً على مشغّل PostgreSQL.

الوحدات الخالصة (fusion, signals) تبقى مستوردة مباشرة لأنها بلا
تبعيات، والباقي يُحمَّل عند الطلب.
"""

from __future__ import annotations

from typing import Any

_LAZY = {
    "QueryProcessor": ".query", "SearchQuery": ".query",
    "ContextResolver": ".context",
    "IntentDetector": ".intent", "QueryIntent": ".intent",
    "SearchCache": ".cache",
    "FullTextSearcher": ".fts",
    "FuzzySearcher": ".fuzzy",
    "SemanticSearcher": ".semantic",
    "RankingEngine": ".ranking",
    "ReRanker": ".reranker",
    "SearchEngine": ".engine",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_path, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(__all__))


__all__ = [
    "ContextResolver", "FullTextSearcher", "FuzzySearcher", "IntentDetector",
    "QueryIntent", "QueryProcessor", "RankingEngine", "ReRanker", "SearchCache",
    "SearchEngine", "SearchQuery", "SemanticSearcher",
]
