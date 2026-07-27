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


def _lazy_import(name: str, module_path: str, package: str):
    """
    يحمّل عند الطلب مع **إظهار السبب الحقيقي** عند الفشل.

    بدون هذا يتحوّل أي خطأ داخل الوحدة (تبعية ناقصة مثلاً) إلى
    AttributeError مبهم، فيراه المستدعي كـ
        ImportError: cannot import name 'X'
    ولا يعرف أن العلّة في مكان آخر تماماً.
    """
    import importlib

    try:
        module = importlib.import_module(module_path, package)
    except Exception as exc:  # التبعية الناقصة تُعلن عن نفسها
        raise ImportError(
            f"تعذّر تحميل {package}{module_path} المطلوب لـ '{name}': "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    try:
        return getattr(module, name)
    except AttributeError as exc:
        raise ImportError(
            f"الوحدة {package}{module_path} لا تعرّف '{name}'"
        ) from exc

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

    value = _lazy_import(name, module_path, __name__)
    globals()[name] = value
    return value



def __dir__() -> list[str]:
    return sorted(set(__all__))


__all__ = [
    "BookImportResult", "BookImportService", "IngestionError", "IngestionManager",
    "Lexicon", "OcrCorrector", "PDFBookImporter", "PDFImportError", "PDFParser",
    "UnsupportedFileTypeError",
]
