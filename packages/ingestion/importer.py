from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from .service import BookImportService


class PDFBookImporter:

    def __init__(self, db: Session):
        self.service = BookImportService(db)

    def import_pdf(self, pdf_path, volume):
        pdf_path = Path(pdf_path)
        return self.service.import_pdf(pdf_path, volume)


BookImportResult = dict

__all__ = [
    "PDFBookImporter",
    "BookImportService",
    "BookImportResult",
]
