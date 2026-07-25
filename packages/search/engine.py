from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from .cache import SearchCache
from .context import ContextResolver
from .fuzzy import FuzzySearcher
from .fts import FullTextSearcher
from .intent import IntentDetector
from .query import QueryProcessor
from .ranking import RankingEngine
from .reranker import ReRanker
from .semantic import SemanticSearcher

class SearchEngine:
    def __init__(self, db: Session):
        self.db = db
        self.processor = QueryProcessor()
        self.intent_detector = IntentDetector()
        self.context = ContextResolver()
        self.fts = FullTextSearcher(db)
        self.fuzzy = FuzzySearcher(db)
        self.semantic = SemanticSearcher()
        self.ranker = RankingEngine()
        self.reranker = ReRanker()
        self.cache = SearchCache(maxsize=256, ttl_seconds=300)

    def _cache_key(self, query: str, limit: int, offset: int) -> str:
        payload = json.dumps({"q": query, "limit": limit, "offset": offset}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _collect_hits(self, candidate_queries: list[str], limit: int) -> tuple[list[dict], dict[str, int]]:
        hits: list[dict] = []
        source_counts: Counter[str] = Counter()

        candidate_queries = [q for q in dict.fromkeys(candidate_queries) if q]
        primary_queries = candidate_queries[:8] or []

        for q in primary_queries:
            for hit in self.fts.search(q, limit=max(20, limit * 2)):
                hits.append(hit)
                source_counts[hit["source"]] += 1
            for hit in self.fuzzy.search(q, limit=max(20, limit * 2)):
                hits.append(hit)
                source_counts[hit["source"]] += 1

        semantic_query = primary_queries[0] if primary_queries else ""
        for hit in self.semantic.search(semantic_query, limit=max(20, limit * 3)):
            hits.append(hit)
            source_counts[hit["source"]] += 1

        return hits, dict(source_counts)

    def search(self, query: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        key = self._cache_key(query, limit, offset)
        cached = self.cache.get(key)
        if cached is not None:
            cached_copy = dict(cached)
            cached_copy["cached"] = True
            return cached_copy

        search_query = self.processor.process(query)
        intent = self.intent_detector.detect(search_query.original)
        context = self.context.resolve(search_query)

        hits, source_counts = self._collect_hits(context.get("candidate_queries", []), limit)
        ranked = self.ranker.rank(search_query, intent, context, hits)
        ranked = self.reranker.rerank(search_query, ranked)

        total = len(ranked.get("results", []))
        results = ranked.get("results", [])[offset : offset + limit]

        response = {
            "query": search_query.original,
            "normalized_query": search_query.normalized,
            "search_form": search_query.search_form,
            "intent": {
                "label": intent.label,
                "confidence": intent.confidence,
                "hints": intent.hints,
            },
            "candidate_queries": context.get("candidate_queries", []),
            "dictionary_suggestions": context.get("dictionary_suggestions", []),
            "phrase_suggestions": context.get("phrase_suggestions", []),
            "entity_suggestions": context.get("entity_suggestions", []),
            "source_counts": source_counts,
            "count": total,
            "results": results,
            "cached": False,
        }

        self.cache.set(key, response)
        return response
