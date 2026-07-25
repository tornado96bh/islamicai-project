from __future__ import annotations

from typing import Any

from packages.learning.dictionary import search_form_text, tokenize_text

from .stopwords import is_generic_phrase


def result_score_threshold(intent: str | None) -> float:
    if intent in {"person", "book"}:
        return 0.10
    if intent == "passage":
        return 0.14
    return 0.15


def _result_text(item: dict[str, Any]) -> str:
    return item.get("best_text") or item.get("text") or item.get("snippet") or ""


def _coverage(query_form: str, text: str) -> float:
    q_tokens = set(tokenize_text(search_form_text(query_form)))
    t_tokens = set(tokenize_text(search_form_text(text)))
    if not q_tokens:
        return 0.0
    return len(q_tokens.intersection(t_tokens)) / len(q_tokens)


def should_keep_result(item: dict[str, Any], query_form: str, intent: str | None) -> bool:
    text = search_form_text(_result_text(item))
    if not text:
        return False

    score = float(item.get("score", 0.0))
    if score < result_score_threshold(intent):
        return False

    if is_generic_phrase(text) and query_form not in text:
        if score < 1.25:
            return False

    if query_form and query_form not in text and _coverage(query_form, text) == 0:
        if intent not in {"person", "book"} and score < 1.55:
            return False

    return True


def prune_results(results: list[dict[str, Any]], query_form: str, intent: str | None) -> list[dict[str, Any]]:
    pruned = []
    for item in results:
        if should_keep_result(item, query_form, intent):
            pruned.append(item)
    return pruned
