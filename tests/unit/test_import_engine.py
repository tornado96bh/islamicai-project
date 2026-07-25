from pathlib import Path

import pytest

from packages.ingestion.parser import PDFParser
from packages.ingestion.utils import infer_language, slugify, split_names


def test_slugify_keeps_arabic():
    assert slugify("وسائل الشيعة") == "وسائل-الشيعة"


def test_split_names():
    assert split_names("A; B, C") == ["A", "B", "C"]


def test_infer_language_arabic():
    assert infer_language("وسائل الشيعة") == "ar"


def test_pdf_parser_missing_file():
    parser = PDFParser()
    with pytest.raises(FileNotFoundError):
        parser.parse(Path("does-not-exist.pdf"))
