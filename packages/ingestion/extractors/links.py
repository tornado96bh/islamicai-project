from __future__ import annotations

from typing import Any


class LinkExtractor:

    def extract(self, pdf: Any):

        links = []

        total = len(pdf)

        for page_number in range(total):

            page = pdf.load_page(page_number)

            for item in page.get_links():

                links.append(
                    {
                        "page": page_number + 1,
                        "data": item,
                    }
                )

        return links
