"""اختبارات الدفعة الثانية عشرة — embeddings حقيقية وأسئلة نظيفة."""

from __future__ import annotations

import pathlib

import pytest

from packages.learning.embeddings_v2 import (
    KNOWN_MODELS,
    HashingEmbedder,
    SemanticEmbedder,
    build_embedder,
)

# تحميل دوال build_golden بلا تبعيات قاعدة البيانات
_SRC = (pathlib.Path(__file__).resolve().parents[2] / "scripts" / "build_golden.py").read_text(
    encoding="utf-8"
)
_ns: dict = {}
exec(_SRC[_SRC.index("def _clean_enough") : _SRC.index("def suggest_from_corpus")], _ns)
_clean_enough = _ns["_clean_enough"]
_distinctive_phrase = _ns["_distinctive_phrase"]


# ===========================================================================
#  التراجع الآمن
# ===========================================================================

def test_fallback_returns_working_embedder():
    """غياب النموذج لا يوقف النظام."""
    e = build_embedder(allow_fallback=True)
    assert e.dimension > 0
    vec = e.vectorize_text("قال رسول الله")
    assert len(vec) == e.dimension


def test_fallback_is_flagged_as_not_semantic():
    """
    التراجع يجب أن يُعلن عن نفسه.

    الطريقة القديمة ليست دلالية: تشابه "النبي محمد" و"الرسول الكريم"
    يساوي صفراً. إخفاء ذلك يجعل الترتيب يبني على ضجيج بلا أن يُلاحظ.
    """
    e = HashingEmbedder()
    assert e.is_semantic is False
    a = e.vectorize_text("النبي محمد")
    b = e.vectorize_text("الرسول الكريم")
    assert e.similarity(a, b) == 0.0, "الـ hashing لا يفهم الترادف"


def test_no_silent_fallback_when_forbidden():
    """السكربتات الحرجة تحتاج فشلاً صريحاً لا تراجعاً صامتاً."""
    try:
        import sentence_transformers  # noqa: F401
        pytest.skip("المكتبة مثبَّتة، لا يمكن اختبار الرفض")
    except ImportError:
        pass
    with pytest.raises(RuntimeError, match="sentence-transformers"):
        build_embedder(allow_fallback=False)


# ===========================================================================
#  توافق الواجهة
# ===========================================================================

@pytest.mark.parametrize("method", ["vectorize_text", "vectorize_many", "similarity"])
def test_interface_matches_old_builder(method):
    """الاستبدال يجب ألا يتطلب تعديل أي مستدعٍ."""
    assert hasattr(HashingEmbedder(), method)
    assert hasattr(SemanticEmbedder("x"), method)


def test_vectors_are_normalised():
    e = HashingEmbedder()
    vec = e.vectorize_text("قال رسول الله صلي الله عليه واله")
    assert abs(sum(x * x for x in vec) - 1.0) < 0.01


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_text_gives_zero_vector(value):
    e = HashingEmbedder()
    vec = e.vectorize_text(value)
    assert len(vec) == e.dimension and all(x == 0.0 for x in vec)


def test_similarity_handles_mismatched_dimensions():
    assert HashingEmbedder.similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_known_model_dimensions_are_declared():
    for name, dim in KNOWN_MODELS.items():
        assert dim in (384, 768, 1024), f"{name} ببُعد غير متوقع"


# ===========================================================================
#  توليد الأسئلة — الحالات الفاسدة من جلسة التحكيم الفعلية
# ===========================================================================

@pytest.mark.parametrize("bad", [
    "................................ ....................... ابن بابويه القمي",
    "......................... السيد ابن طاووس",
    "اسم الله . . . ....... 01 768 678 033",
    "] 989 1 [ محمد بن يعقوب",
    "قصير",
])
def test_polluted_queries_rejected(bad):
    """
    هذي أسئلة حقيقية أنتجتها النسخة السابقة لأنها قرأت entities.json
    المخزَّن بلا ترشيح.
    """
    assert not _clean_enough(bad)


@pytest.mark.parametrize("good", [
    "قال رسول الله صلي الله عليه واله : الما يطهر ولا يطهر ابدا حتي يتغير",
    "عن ابي عبد الله عليه السلام قال : الوضو شطر الايمان وهو نور",
    "باب استحباب تجديد الوضو من غير حدث لكل صلاه",
])
def test_clean_text_accepted(good):
    assert _clean_enough(good)


def test_phrase_skips_formulaic_opening():
    """
    اقتطاع الوسط أنتج "الله عليه واله الما يطهر" — نصفها صيغة صلاة.
    النافذة المختارة يجب أن تتجنب النمطي.
    """
    phrase = _distinctive_phrase(
        "قال رسول الله صلي الله عليه واله : الما يطهر ولا يطهر ابدا حتي يتغير", n=5
    )
    assert "يطهر" in phrase
    assert not phrase.startswith("الله عليه")


def test_phrase_length_respected():
    for n in (3, 5, 7):
        out = _distinctive_phrase(
            "عن ابي عبد الله عليه السلام قال الوضو شطر الايمان وهو نور علي نور", n=n
        )
        assert len(out.split()) <= n


def test_phrase_on_short_text():
    assert _distinctive_phrase("نص قصير جدا", n=5) == "نص قصير جدا"
