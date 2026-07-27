"""
اختبارات الدفعة الثامنة عشرة — إصلاح عطب الاستيراد.

العطب: سُلّمت ملفات `__init__.py` فارغة كعلامات حزم، فمحا مثبِّتُها
ملفاتِ الاستيراد الكسول الحقيقية، وانهار الخادم عند الإقلاع.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

LAZY_PACKAGES = [
    "packages/ingestion/__init__.py",
    "packages/search/__init__.py",
    "packages/learning/__init__.py",
]


# ===========================================================================
#  1) الملف الفارغ — العطب الصامت
# ===========================================================================

@pytest.mark.parametrize("rel", LAZY_PACKAGES)
def test_lazy_init_files_are_not_empty(rel):
    """
    الملف الفارغ صحيح نحوياً وقاتل عند الإقلاع: يمحو __getattr__
    فتفشل كل الاستيرادات التي تعتمد عليه.
    """
    p = REPO_ROOT / rel
    assert p.exists(), f"{rel} مفقود"
    assert p.stat().st_size > 50, f"{rel} فارغ — العطب عاد"


@pytest.mark.parametrize("rel", LAZY_PACKAGES)
def test_lazy_init_declares_getattr(rel):
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    assert "__getattr__" in text
    assert "_LAZY" in text


# ===========================================================================
#  2) الأسماء التي تحتاجها الراوترات
# ===========================================================================

@pytest.mark.parametrize("module_name,names", [
    ("packages.ingestion", ["BookImportResult", "IngestionManager", "PDFParser",
                            "BookImportService", "PDFBookImporter"]),
    ("packages.search", ["SearchEngine", "RankingEngine", "FullTextSearcher",
                         "FuzzySearcher", "SemanticSearcher", "IntentDetector"]),
    ("packages.learning", ["LearningTrainer", "EntityLearner"]),
])
def test_declared_names_are_reachable(module_name, names):
    """
    `from packages.ingestion import BookImportResult` هو ما فشل عند
    إقلاع الخادم. كل اسم مُعلَن يجب أن يكون قابلاً للوصول أو أن
    يفشل بسبب **تبعية** لا بسبب غياب التعريف.
    """
    module = importlib.import_module(module_name)
    for name in names:
        assert name in module.__all__, f"{name} غير معلَن في __all__"
        try:
            getattr(module, name)
        except ImportError as exc:
            # تبعية ناقصة في بيئة الاختبار — ليست عطباً في الكود
            assert "تعذّر تحميل" in str(exc) or "No module named" in str(exc)
        except AttributeError:
            pytest.fail(f"{module_name}.{name} غير معرَّف")


# ===========================================================================
#  3) رسالة الفشل تدلّ على السبب الحقيقي
# ===========================================================================

def test_missing_dependency_names_the_real_cause():
    """
    بلا هذا يتحوّل نقصُ تبعية إلى
        ImportError: cannot import name 'X'
    فيبحث المطوّر عن X وهي موجودة، والعلّة في مكان آخر.
    """
    import packages.ingestion as pkg

    try:
        pkg.PDFParser
    except ImportError as exc:
        message = str(exc)
        assert "تعذّر تحميل" in message
        assert "packages.ingestion" in message


def test_unknown_name_raises_attribute_error():
    import packages.ingestion as pkg

    with pytest.raises(AttributeError):
        pkg.NoSuchThing


# ===========================================================================
#  4) الأدوات الخفيفة تبقى بلا تبعيات ثقيلة
# ===========================================================================

def test_light_helpers_need_no_heavy_dependency():
    """
    الغرض الأصلي من الاستيراد الكسول: استيراد دالة تطبيع لا يوقظ
    PyMuPDF ولا PostgreSQL.
    """
    from packages.learning import normalize_surface_text, search_form_text

    assert callable(normalize_surface_text) and callable(search_form_text)


def test_database_engine_still_lazy():
    """
    استيراد الوحدة يجب ألا يبني محركاً. ولو تعذّر الاستيراد لغياب
    مشغّل قاعدة البيانات، فذلك عن البيئة لا عن الكود — ويُتخطّى
    صراحةً بدل أن يُعدّ فشلاً.
    """
    try:
        from packages.database import session
    except ImportError as exc:
        pytest.skip(f"مشغّل قاعدة البيانات غير متاح: {exc}")

    assert session.get_engine.cache_info().currsize == 0


# ===========================================================================
#  5) الحارس نفسه
# ===========================================================================

def test_verifier_script_exists_and_compiles():
    """بوابة تمنع تكرار العطب قبل النشر."""
    p = REPO_ROOT / "scripts" / "verify_imports.py"
    assert p.exists()
    compile(p.read_text(encoding="utf-8"), str(p), "exec")


def test_verifier_declares_the_empty_init_check():
    text = (REPO_ROOT / "scripts" / "verify_imports.py").read_text(encoding="utf-8")
    assert "MUST_NOT_BE_EMPTY" in text
    for rel in LAZY_PACKAGES:
        assert rel in text
