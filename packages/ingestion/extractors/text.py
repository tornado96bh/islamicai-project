from __future__ import annotations

from typing import Any


class TextExtractor:

    def extract(self, pdf: Any):

        pages = []

        total = len(pdf)

        for index in range(total):

            page = pdf.load_page(index)

            text = page.get_text("text") or ""

            pages.append(
                {
                    "page": index + 1,
                    "text": text,
                    "characters": len(text),
                    "words": len(text.split()),
                }
            )

        return pages
