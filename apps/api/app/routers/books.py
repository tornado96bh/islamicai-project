from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from apps.api.app.deps import db_session
from packages.ingestion import BookImportResult, IngestionManager
from packages.services import BookService
from packages.ingestion.utils import slugify

router = APIRouter()


class BookCreate(BaseModel):
    title: str
    slug: str | None = None
    language: str = "ar"
    category: str | None = None
    description: str | None = None
    isbn: str | None = None


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str | None = None
    language: str
    category: str | None = None
    isbn: str | None = None


@router.get("", response_model=list[BookRead])
def list_books(db: Session = Depends(db_session)):
    return BookService(db).all()


@router.get("/{book_id}", response_model=BookRead)
def get_book(book_id: UUID, db: Session = Depends(db_session)):
    book = BookService(db).get(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.post("", response_model=BookRead, status_code=201)
def create_book(payload: BookCreate, db: Session = Depends(db_session)):
    slug = payload.slug or slugify(payload.title)
    if slug == "untitled":
        slug = f"book-{uuid4().hex[:12]}"
    return BookService(db).create(
        title=payload.title,
        slug=slug,
        language=payload.language,
        category=payload.category,
        description=payload.description,
        isbn=payload.isbn,
        is_public=True,
        metadata_json={},
        short_title=payload.title[:255],
        original_title=payload.title,
    )


@router.post("/import/pdf", response_model=BookImportResult, status_code=201)
def import_pdf(
    volume_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        from packages.services import VolumeService
        volume = VolumeService(db).get(volume_id)
        if volume is None:
            raise HTTPException(status_code=404, detail="Volume not found")

        return IngestionManager(db).import_pdf(tmp_path, volume)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass



