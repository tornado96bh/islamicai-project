from __future__ import annotations

from typing import Any


class WordExtractor:

    def extract(self, pdf: Any):

        words = []

        total = len(pdf)

        for page_number in range(total):

            page = pdf.load_page(page_number)

            for word in page.get_text("words"):

                words.append(
                    {
                        "page": page_number + 1,
                        "bbox": {
                            "x0": word[0],
                            "y0": word[1],
                            "x1": word[2],
                            "y1": word[3],
                        },
                        "text": word[4],
                    }
                )

        return words
