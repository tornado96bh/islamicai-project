from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DocumentMetadata:
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    keywords: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    pages: int = 0


class MetadataExtractor:
    def extract(self, pdf: Any) -> DocumentMetadata:
        meta = getattr(pdf, "metadata", {}) or {}

        try:
            page_count = len(pdf)
        except Exception:
            page_count = 0

        return DocumentMetadata(
            title=meta.get("title"),
            author=meta.get("author"),
            subject=meta.get("subject"),
            creator=meta.get("creator"),
            producer=meta.get("producer"),
            keywords=meta.get("keywords"),
            creation_date=meta.get("creationDate"),
            modification_date=meta.get("modDate"),
            pages=page_count,
        )
