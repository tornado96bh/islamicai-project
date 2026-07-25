from __future__ import annotations

from collections.abc import Iterable

from packages.learning.context import ContextLearner
from packages.learning.dictionary import DictionaryLearner, search_form_text
from packages.learning.entities import EntityLearner
from packages.learning.phrases import PhraseLearner

from .query import SearchQuery
from .stopwords import filter_candidate_phrase, is_generic_query

def _unique(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        item = search_form_text(item)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out

class ContextResolver:
    def __init__(self):
        self.dictionary = DictionaryLearner()
        self.phrases = PhraseLearner()
        self.entities = EntityLearner()
        self.context = ContextLearner()

    def resolve(self, query: SearchQuery) -> dict:
        q = query.search_form or query.normalized or query.original

        dictionary_suggestions = self.dictionary.suggest(q, limit=8)
        phrase_suggestions = self.phrases.suggest(q, limit=8)
        entity_suggestions = self.entities.suggest(q, limit=8)

        candidate_queries: list[str] = [q, query.normalized, query.original]

        for item in dictionary_suggestions:
            word = item.get("word")
            if word and filter_candidate_phrase(word, q):
                candidate_queries.append(word)

        for item in phrase_suggestions:
            phrase = item.get("phrase")
            if phrase and filter_candidate_phrase(phrase, q):
                candidate_queries.append(phrase)

        for item in entity_suggestions:
            label = item.get("label")
            if label and filter_candidate_phrase(label, q):
                candidate_queries.append(label)

        for token in query.search_tokens[:5]:
            try:
                neighbor_words = self.context.neighbors(token, limit=5)
            except Exception:
                neighbor_words = []
            for item in neighbor_words:
                word = item.get("word")
                if word and filter_candidate_phrase(word, q):
                    candidate_queries.append(word)

        if is_generic_query(query.search_tokens) and len(query.search_tokens) <= 2:
            candidate_queries = [q] + [c for c in candidate_queries[1:] if len(c.split()) >= 2]

        candidate_queries = _unique(candidate_queries)

        return {
            "query": q,
            "dictionary_suggestions": dictionary_suggestions,
            "phrase_suggestions": phrase_suggestions,
            "entity_suggestions": entity_suggestions,
            "candidate_queries": candidate_queries,
        }
