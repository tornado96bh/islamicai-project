from pathlib import Path

from packages.database.session import SessionLocal
from packages.ingestion.manager import IngestionManager

db = SessionLocal()

try:
    pdf = Path("sample.pdf")

    result = IngestionManager(db).import_pdf(
        pdf_path=pdf,
        title="PDF Test",
        edition_name="First Edition",
        volume_number=1,
    )

    print("=" * 60)
    print("IMPORT SUCCESS")
    print("=" * 60)
    print(result.keys())

finally:
    db.close()
