from __future__ import annotations

from typing import Any


class ImagesExtractor:
    def extract(self, pdf: Any):
        images = []

        try:
            total = len(pdf)
        except Exception:
            return images

        for page_index in range(total):
            page = pdf.load_page(page_index)
            try:
                page_images = page.get_images(full=True) or []
            except Exception:
                continue

            for img in page_images:
                images.append(
                    {
                        "page": page_index + 1,
                        "xref": img[0],
                        "width": img[2] if len(img) > 2 else None,
                        "height": img[3] if len(img) > 3 else None,
                        "bpc": img[4] if len(img) > 4 else None,
                    }
                )

        return images
