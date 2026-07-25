from __future__ import annotations

import math
from typing import Iterable

from packages.learning.dictionary import search_form_text, tokenize_text
from .stopwords import is_generic_phrase, is_stopword


def normalized_tokens(text: str | None) -> list[str]:
    return [t for t in tokenize_text(search_form_text(text)) if t]


def overlap_ratio(query_tokens: Iterable[str], text: str | None) -> float:
    q = [t for t in query_tokens if t]
    if not q:
        return 0.0
    s = set(normalized_tokens(text))
    return len(s.intersection(q)) / max(len(set(q)), 1)


def generic_density(text: str | None) -> float:
    tokens = normalized_tokens(text)
    if not tokens:
        return 1.0
    generic = sum(1 for t in tokens if is_stopword(t))
    return generic / len(tokens)


def phrase_quality(text: str | None) -> float:
    t = search_form_text(text)
    if not t:
        return 0.0
    tokens = normalized_tokens(t)
    if not tokens:
        return 0.0
    if is_generic_phrase(t):
        return 0.0
    length = len(tokens)
    score = min(length / 4.0, 1.0)
    score += min(len(set(tokens)) / max(length, 1), 1.0) * 0.35
    score += math.log1p(length) / 10.0
    return score


def source_bonus(sources: Iterable[str]) -> float:
    unique = len(set(sources))
    return min(unique, 4) * 0.08


def exact_bonus(query_form: str, text: str | None) -> float:
    q = search_form_text(query_form)
    t = search_form_text(text)
    if not q or not t:
        return 0.0
    if q == t:
        return 2.25
    if q in t:
        return 1.35
    return 0.0


def token_coverage_boost(query_tokens: Iterable[str], text: str | None) -> float:
    q = [t for t in query_tokens if t and not is_stopword(t)]
    if not q:
        return 0.0
    coverage = overlap_ratio(q, text)
    return coverage * 1.35


def generic_penalty(text: str | None) -> float:
    density = generic_density(text)
    if density <= 0.15:
        return 0.0
    return min(0.65, density * 0.75)


def source_weight(source: str) -> float:
    return {
        "fts": 1.0,
        "fuzzy": 0.78,
        "semantic": 0.9,
    }.get(source, 0.8)
