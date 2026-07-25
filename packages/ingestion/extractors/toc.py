from __future__ import annotations


class TOCExtractor:
    def extract(self, pdf):
        try:
            return pdf.get_toc() or []
        except Exception:
            return []
