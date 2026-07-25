from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from packages.database.models import Book, Edition, Volume
from packages.learning.trainer import LearningTrainer

from .service import BookImportService
from .utils import slugify

class IngestionManager:
    def __init__(self, db: Session):
        self.db = db
        self.service = BookImportService(db)

    def import_pdf(
        self,
        pdf_path: str | Path,
        title: str,
        edition_name: str = "First Edition",
        volume_number: int = 1,
    ):
        pdf_path = Path(pdf_path)

        book = Book(
            title=title,
            slug=f"{slugify(title)}-{uuid4().hex[:8]}",
            short_title=title,
            original_title=title,
            language="ar",
            is_public=True,
            metadata_json={},
        )
        self.db.add(book)
        self.db.flush()

        edition = Edition(book_id=book.id, edition_number=1)
        self.db.add(edition)
        self.db.flush()

        volume = Volume(edition_id=edition.id, volume_number=volume_number)
        self.db.add(volume)
        self.db.flush()

        result = self.service.import_pdf(pdf_path, volume)
        self.db.commit()

        # ---------------------------------------------------------------
        # التدريب لم يعد يعمل داخل مسار الاستيراد.
        #
        # السبب: train_book() كان يعيد بناء كل ملفات التعلّم ويرفع إلى
        # Qdrant داخل الطلب المتزامن، وهو عمل ثقيل مكانه Worker Service
        # حسب الماستر §4. وكان أيضاً يمحو متجهات الكتب الأخرى.
        #
        # للتدريب اليدوي بعد الاستيراد:
        #     python scripts/train_learning.py
        # ---------------------------------------------------------------
        learning_summary = None
        learning_error = None

        return {
            "book": book,
            "edition": edition,
            "volume": volume,
            "result": result,
            "learning_summary": learning_summary,
            "learning_error": learning_error,
        }
