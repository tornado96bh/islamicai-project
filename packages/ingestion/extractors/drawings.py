from __future__ import annotations

from typing import Any


class DrawingExtractor:

    def extract(self, pdf: Any):

        drawings = []

        total = len(pdf)

        for page_number in range(total):

            page = pdf.load_page(page_number)

            try:
                data = page.get_drawings()
            except Exception:
                data = []

            drawings.append(
                {
                    "page": page_number + 1,
                    "count": len(data),
                    "items": data,
                }
            )

        return drawings
