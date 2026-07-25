from __future__ import annotations

from typing import Any


class BlockExtractor:

    def extract(self, pdf: Any):

        results = []

        total = len(pdf)

        for page_number in range(total):

            page = pdf.load_page(page_number)

            blocks = page.get_text("blocks")

            order = 0

            for block in blocks:

                order += 1

                results.append(
                    {
                        "page": page_number + 1,
                        "order": order,
                        "bbox": {
                            "x0": block[0],
                            "y0": block[1],
                            "x1": block[2],
                            "y1": block[3],
                        },
                        "text": block[4],
                    }
                )

        return results
