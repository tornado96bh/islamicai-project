from __future__ import annotations

from packages.learning.dictionary import search_form_text
from packages.learning.embeddings import EmbeddingBuilder

class ReRanker:
    def __init__(self):
        self.embedding = EmbeddingBuilder(dimension=256)

    def rerank(self, search_query, bundle: dict) -> dict:
        qvec = self.embedding.vectorize_text(search_query.search_form or search_query.normalized or search_query.original)

        for item in bundle.get("results", []):
            doc = " ".join(
                part
                for part in [
                    item.get("book_title") or "",
                    item.get("best_snippet") or item.get("snippet") or "",
                    item.get("best_text") or item.get("text") or "",
                ]
                if part
            ).strip()

            if not doc:
                continue

            dvec = self.embedding.vectorize_text(doc)
            sim = self.embedding.similarity(qvec, dvec)
            boost = sim * 0.95

            search_text = search_form_text(doc)
            if search_query.search_form and search_query.search_form in search_text:
                boost += 0.4
            if search_query.phrases:
                for phrase in search_query.phrases[:4]:
                    if phrase in search_text:
                        boost += 0.15

            item["score"] = round(float(item.get("score", 0.0)) + boost, 6)

        bundle["results"].sort(
            key=lambda x: (
                x["score"],
                x.get("book_title") or "",
                x.get("page_number") or 0,
                x.get("best_element_order") or 0,
            ),
            reverse=True,
        )
        return bundle
