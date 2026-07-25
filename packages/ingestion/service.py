from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from packages.database.models import Page
from packages.database.models import PageElement
from packages.database.models import PageImage

from .parser import PDFParser
from .pipeline import IngestionPipeline


class BookImportService:

    def __init__(self, db: Session):

        self.db = db

        self.parser = PDFParser()

        self.pipeline = IngestionPipeline()

    def import_pdf(self, pdf_path: str | Path, volume):

        pdf = self.parser.parse(pdf_path)

        try:

            result = self.pipeline.run(pdf)

        finally:

            pdf.close()

        pages_lookup = {}

        for page_data in result["pages"]:

            page = Page(

                volume_id=volume.id,

                page_number=page_data["number"],

            )

            self.db.add(page)

            self.db.flush()

            pages_lookup[page.page_number] = page

        for block in result["blocks"]:

            page = pages_lookup.get(block["page"])

            if page is None:
                continue

            self.db.add(

                PageElement(

                    page_id=page.id,

                    element_type="text",

                    element_order=block["order"],

                    bbox=block["bbox"],

                    text=block["text"],

                )

            )

        for image in result["images"]:

            page = pages_lookup.get(image["page"])

            if page is None:
                continue

            self.db.add(

                PageImage(

                    page_id=page.id,

                    image_path=f"images/page_{image['page']}_{image['xref']}.png",

                    width=image.get("width"),

                    height=image.get("height"),

                    dpi=300,

                )

            )

        self.db.commit()

        return result
