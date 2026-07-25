from pathlib import Path

from sqlalchemy.orm import Session

from packages.ingestion.manager import IngestionManager


def run(db: Session, volume):

    manager = IngestionManager(db)

    result = manager.import_pdf(

        Path("sample.pdf"),

        volume,

    )

    print(result["metadata"])

    print(len(result["pages"]))

    print(len(result["blocks"]))

    print(len(result["images"]))
