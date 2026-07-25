from __future__ import annotations

from typing import Any


class PagesExtractor:
    def extract(self, pdf: Any):
        pages = []

        try:
            total = len(pdf)
        except Exception:
            return pages

        for index in range(total):
            page = pdf.load_page(index)
            text = page.get_text("text") or ""
            blocks = page.get_text("blocks") or []
            pages.append(
                {
                    "number": index + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "rotation": page.rotation,
                    "text": text,
                    "text_len": len(text.strip()),
                    "blocks": blocks,
                }
            )

        return pages
