"""
packages.ingestion — استيراد كسول.

كان هذا الملف يستورد PDFParser تلقائياً، وهو يسحب `fitz` (PyMuPDF).
فأي استيراد لأداة نصية خفيفة مثل OcrCorrector كان يتطلب PyMuPDF،
وينهار جمع الاختبارات بدونه.

المكوّنات الثقيلة تُحمَّل عند أول طلب عبر __getattr__ (PEP 562)،
فيبقى `from packages.ingestion import PDFParser` يعمل بلا تغيير.
"""

from __future__ import annotations

from typing import Any

from .exceptions import IngestionError, PDFImportError, UnsupportedFileTypeError

_LAZY = {
    "IngestionManager": ".manager",
    "PDFParser": ".parser",
    "BookImportService": ".service",
    "PDFBookImporter": ".importer",
    "BookImportResult": ".importer",
    "OcrCorrector": ".ocr_corrector",
    "Lexicon": ".ocr_corrector",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_path, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(__all__))


__all__ = [
    "BookImportResult", "BookImportService", "IngestionError", "IngestionManager",
    "Lexicon", "OcrCorrector", "PDFBookImporter", "PDFImportError", "PDFParser",
    "UnsupportedFileTypeError",
]
