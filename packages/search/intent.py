from __future__ import annotations

from dataclasses import dataclass

from packages.learning.dictionary import search_form_text, tokenize_text
from .stopwords import is_generic_query

@dataclass(slots=True)
class QueryIntent:
    label: str
    confidence: float
    hints: list[str]

class IntentDetector:
    def detect(self, query: str) -> QueryIntent:
        q = search_form_text(query)
        tokens = tokenize_text(q)
        text = q

        hints: list[str] = []
        label = "general"
        confidence = 0.55

        if any(p in text for p in ("من هو", "من هي", "ترجم", "تعريف", "من هذا", "من هذه")):
            label = "entity"
            confidence = 0.78
            hints.append("identity")
        if any(p in text for p in ("كتاب", "مؤلف", "طبعة", "إصدار", "ناشر", "باب", "فصل", "جزء", "مجلد")):
            label = "bibliography"
            confidence = max(confidence, 0.72)
            hints.append("bibliography")
        if any(p in text for p in ("آية", "سورة", "قرآن", "المصحف")):
            label = "quran"
            confidence = max(confidence, 0.8)
            hints.append("quran")
        if any(p in text for p in ("حديث", "رواية", "سند", "إسناد", "راوي", "أبواب")):
            label = "hadith"
            confidence = max(confidence, 0.8)
            hints.append("hadith")
        if len(tokens) == 1 and not is_generic_query(tokens):
            label = "entity"
            confidence = max(confidence, 0.72)
            hints.append("single-term")
        if len(tokens) <= 2 and label == "general":
            confidence = min(0.65, confidence)

        return QueryIntent(label=label, confidence=round(confidence, 2), hints=hints)
