from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable

from .dictionary import search_form_text, tokenize_text


@dataclass(slots=True)
class EmbeddingVector:
    values: list[float]


class EmbeddingBuilder:
    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def _hash(self, token: str) -> int:
        digest = hashlib.sha1(token.encode("utf-8", errors="ignore")).digest()
        return int.from_bytes(digest[:4], "big") % self.dimension

    def vectorize_tokens(self, tokens: Iterable[str]) -> EmbeddingVector:
        vector = [0.0] * self.dimension

        for token in tokens:
            token = search_form_text(token)
            if not token:
                continue
            idx = self._hash(token)
            vector[idx] += 1.0
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    tri = token[i : i + 3]
                    vector[self._hash(f"tri:{tri}")] += 0.35

        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return EmbeddingVector(values=vector)

    def vectorize_text(self, text: str | None) -> EmbeddingVector:
        return self.vectorize_tokens(tokenize_text(search_form_text(text)))

    def average(self, vectors: Iterable[EmbeddingVector | list[float]]) -> EmbeddingVector:
        values = list(vectors)
        if not values:
            return EmbeddingVector(values=[0.0] * self.dimension)

        acc = [0.0] * self.dimension
        count = 0

        for vec in values:
            data = vec.values if isinstance(vec, EmbeddingVector) else vec
            if len(data) != self.dimension:
                continue
            for i, item in enumerate(data):
                acc[i] += float(item)
            count += 1

        if count == 0:
            return EmbeddingVector(values=[0.0] * self.dimension)

        acc = [v / count for v in acc]
        norm = math.sqrt(sum(v * v for v in acc))
        if norm > 0:
            acc = [v / norm for v in acc]
        return EmbeddingVector(values=acc)

    @staticmethod
    def similarity(a: EmbeddingVector | list[float], b: EmbeddingVector | list[float]) -> float:
        av = a.values if isinstance(a, EmbeddingVector) else a
        bv = b.values if isinstance(b, EmbeddingVector) else b
        if len(av) != len(bv) or not av:
            return 0.0
        dot = sum(x * y for x, y in zip(av, bv))
        na = math.sqrt(sum(x * x for x in av))
        nb = math.sqrt(sum(y * y for y in bv))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
