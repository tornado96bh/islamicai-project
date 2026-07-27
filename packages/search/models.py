from __future__ import annotations

from typing import Any
import re

from packages.learning.dictionary import search_form_text

def clip_text(text: str | None, limit: int = 320) -> str:
    text = text or ""
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"

def hit_key(hit: dict[str, Any]) -> str:
    return f"{hit.get('page_id')}::{hit.get('element_id') or 'page'}"

def build_element_hit(element: Any, score: float, source: str, reason: str = "") -> dict[str, Any]:
    page = getattr(element, "page", None)
    volume = getattr(page, "volume", None) if page is not None else None
    edition = getattr(volume, "edition", None) if volume is not None else None
    book = getattr(edition, "book", None) if edition is not None else None

    # text_raw مقدّس: هو ما يُعرض ويُستشهد به، بكل حركاته وهمزاته.
    raw_text = (
        getattr(element, "text_raw", None) or getattr(element, "text", "") or ""
    )
    snippet = clip_text(raw_text)

    # النص المفهرَس المصحَّح. حسابه من الخام هنا كان يعيد إظهار عطب
    # OCR في الواجهة رغم أن الفهرس نظيف — لأن التصحيح يجري في الملء
    # لا في التطبيع اللحظي.
    indexed_text = getattr(element, "text_normalized", None)

    return {
        "source": source,
        "reason": reason,
        "score": float(score),
        "page_id": str(getattr(page, "id", "")) if page is not None else None,
        "page_number": getattr(page, "page_number", None) if page is not None else None,
        "volume_id": str(getattr(page, "volume_id", "")) if page is not None else None,
        "volume_number": getattr(volume, "volume_number", None) if volume is not None else None,
        "edition_id": str(getattr(edition, "id", "")) if edition is not None else None,
        "edition_number": getattr(edition, "edition_number", None) if edition is not None else None,
        "book_id": str(getattr(book, "id", "")) if book is not None else None,
        "book_title": getattr(book, "title", None) if book is not None else None,
        "element_id": str(getattr(element, "id", "")),
        "element_type": getattr(element, "element_type", None),
        "element_order": getattr(element, "element_order", None),
        "text": raw_text,
        "snippet": snippet,
        "search_text": indexed_text if indexed_text else search_form_text(raw_text),
        # الصيغة المقروءة: بلا تمديد ولا تفكّك، بكل الحركات والهمزات
        # والنقاط. هذا ما يُعرض للقارئ؛ و text يبقى الأصل للاستشهاد.
        "text_display": getattr(element, "text_display", None) or raw_text,
        "hadith_number": getattr(element, "hadith_number", None),
        "isnad_text": getattr(element, "isnad_text", None),
        "matn_text": getattr(element, "matn_text", None),
        "split_confidence": getattr(element, "split_confidence", None),
        "sources": [source],
        "reasons": [reason] if reason else [],
        "best_element_id": str(getattr(element, "id", "")),
        "best_element_type": getattr(element, "element_type", None),
        "best_element_order": getattr(element, "element_order", None),
        "best_snippet": snippet,
        "best_text": raw_text,
    }

def build_page_hit(profile: dict[str, Any], score: float, source: str, reason: str = "") -> dict[str, Any]:
    raw_text = profile.get("sample_text", "") or ""
    snippet = clip_text(raw_text)

    return {
        "source": source,
        "reason": reason,
        "score": float(score),
        "page_id": str(profile.get("page_id") or ""),
        "page_number": profile.get("page_number"),
        "volume_id": profile.get("volume_id"),
        "volume_number": profile.get("volume_number"),
        "edition_id": profile.get("edition_id"),
        "edition_number": profile.get("edition_number"),
        "book_id": profile.get("book_id"),
        "book_title": profile.get("book_title"),
        "element_id": None,
        "element_type": "page",
        "element_order": None,
        "text": raw_text,
        "snippet": snippet,
        "search_text": search_form_text(raw_text),
        "sources": [source],
        "reasons": [reason] if reason else [],
        "best_element_id": None,
        "best_element_type": "page",
        "best_element_order": None,
        "best_snippet": snippet,
        "best_text": raw_text,
    }
