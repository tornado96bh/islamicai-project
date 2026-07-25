from __future__ import annotations

from collections import Counter, defaultdict

from packages.learning.dictionary import search_form_text, tokenize_text
from .models import hit_key

class RankingEngine:
    def __init__(self):
        self.source_weights = {
            "fts": 1.9,
            "fuzzy": 1.25,
            "semantic": 1.1,
        }

    def _score_hit(self, search_query, intent, context: dict, bucket: dict) -> float:
        query_form = search_query.search_form or search_query.normalized or search_query.original
        search_text = search_form_text(bucket.get("best_text") or bucket.get("text") or "")
        query_tokens = set(search_query.search_tokens or tokenize_text(search_form_text(search_query.original)))

        base = float(bucket.get("score", 0.0))
        sources = bucket.get("sources") or []
        source_counts = bucket.get("source_counts") or {}

        for src in sources:
            base += self.source_weights.get(src, 0.05) * 0.1

        if query_form and search_text == query_form:
            base += 3.0
        if query_form and query_form in search_text:
            base += 1.7

        overlap = len(set(tokenize_text(search_text)) & query_tokens)
        base += overlap * 0.15

        if bucket.get("book_title") and search_form_text(bucket["book_title"]) in query_form:
            base += 0.7

        if intent and intent.label in {"hadith", "quran", "bibliography", "entity"}:
            if intent.label == "hadith" and any(k in search_text for k in ("قال", "عن", "حدث", "روى")):
                base += 0.4
            if intent.label == "quran" and any(k in search_text for k in ("آية", "سورة", "القرآن", "المصحف")):
                base += 0.6
            if intent.label == "bibliography" and any(k in search_text for k in ("كتاب", "مجلد", "جزء", "باب")):
                base += 0.4

        # Reward diverse but not spammy source agreement.
        base += min(len(set(sources)), 4) * 0.08
        base += min(sum(source_counts.values()), 5) * 0.03

        # Penalize generic outputs a bit if the content is too thin.
        if len(query_tokens) <= 1 and len(search_text.split()) < 3:
            base -= 0.15

        return round(base, 6)

    def rank(self, search_query, intent, context: dict, hits: list[dict]) -> dict:
        merged: dict[str, dict] = {}

        candidate_forms = [search_form_text(x) for x in context.get("candidate_queries", []) if search_form_text(x)]
        candidate_forms = list(dict.fromkeys(candidate_forms))
        query_form = search_query.search_form or search_query.normalized or search_query.original

        for hit in hits:
            key = hit_key(hit)
            bucket = merged.get(key)
            if bucket is None:
                bucket = dict(hit)
                bucket["score"] = float(hit.get("score", 0.0))
                bucket["sources"] = list(hit.get("sources") or [hit.get("source")])
                bucket["reasons"] = list(hit.get("reasons") or ([hit.get("reason")] if hit.get("reason") else []))
                bucket["source_counts"] = Counter(bucket["sources"])
                bucket["hit_count"] = 1
                merged[key] = bucket
            else:
                bucket["score"] += float(hit.get("score", 0.0))
                source = hit.get("source")
                if source:
                    bucket["sources"].append(source)
                    bucket["source_counts"][source] += 1
                reason = hit.get("reason")
                if reason:
                    bucket["reasons"].append(reason)
                bucket["hit_count"] = bucket.get("hit_count", 1) + 1

            if hit.get("element_id") and (
                not bucket.get("best_element_id")
                or float(hit.get("score", 0.0)) > float(bucket.get("best_element_score", 0.0))
            ):
                bucket["best_element_id"] = hit.get("element_id")
                bucket["best_element_type"] = hit.get("element_type")
                bucket["best_element_order"] = hit.get("element_order")
                bucket["best_text"] = hit.get("text")
                bucket["best_snippet"] = hit.get("snippet")
                bucket["best_element_score"] = float(hit.get("score", 0.0))

            if hit.get("element_id") is None and not bucket.get("best_text"):
                bucket["best_text"] = hit.get("text")
                bucket["best_snippet"] = hit.get("snippet")

        ranked: list[dict] = []
        for bucket in merged.values():
            bucket["score"] = self._score_hit(search_query, intent, context, bucket)
            search_text = search_form_text(bucket.get("best_text") or bucket.get("text") or "")
            for candidate in candidate_forms[:6]:
                if candidate and candidate in search_text:
                    bucket["score"] += 0.25
            bucket["score"] = round(float(bucket["score"]), 6)
            bucket["sources"] = sorted(set(bucket.get("sources") or []))
            bucket["reasons"] = [r for r in bucket.get("reasons") or [] if r]
            bucket["source_counts"] = dict(bucket.get("source_counts") or {})
            bucket["search_text"] = search_text
            ranked.append(bucket)

        ranked.sort(
            key=lambda x: (
                x["score"],
                x.get("book_title") or "",
                x.get("page_number") or 0,
                x.get("best_element_order") or 0,
            ),
            reverse=True,
        )

        return {
            "count": len(ranked),
            "results": ranked,
        }
