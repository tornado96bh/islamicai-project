from __future__ import annotations

from pathlib import Path

import fitz


class PDFParser:
    """
    Thin wrapper around PyMuPDF.

    This class returns the opened fitz.Document.
    All extraction is performed later by the IngestionPipeline.
    """

    def parse(self, pdf_path: str | Path):

        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(pdf_path)

        return fitz.open(str(pdf_path))
