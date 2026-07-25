from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class PageElement(BaseModel):
    element_id: str
    type: Literal["sanad", "matn", "hashiya", "ta'leeq", "heading", "citation"]
    text_raw: str
    text_normalized: str
    bounding_box: BoundingBox
    ocr_confidence: float = Field(ge=0, le=1)
    layout_confidence: float = Field(ge=0, le=1)
    speaker: Optional[str] = None


class Narrator(BaseModel):
    narrator_id: str
    name_raw: str
    name_normalized: str
    kunya: Optional[str] = None
    laqab: Optional[str] = None
    alt_names: List[str] = []


class Source(BaseModel):
    book: str
    edition: Optional[str] = None
    editor: Optional[str] = None
    volume: Optional[str] = None
    printed_page: Optional[str] = None
    file_page: Optional[str] = None
    excerpt: str
    element_type: Literal["matn", "sanad", "hashiya", "ta'leeq", "citation"]
    confidence: float = Field(ge=0, le=1)


class EvidenceBundle(BaseModel):
    question: str
    sources: List[Source]
    ambiguity_flag: bool = False
    warnings: List[str] = []


class FinalAnswer(BaseModel):
    schema_version: str = "3.0.0"
    pipeline_version: str = "3.0.0"
    answer_summary: str
    confidence: float = Field(ge=0, le=1)
    ambiguity_flag: bool = False
    warnings: List[str] = []
    sources: List[Source] = []
