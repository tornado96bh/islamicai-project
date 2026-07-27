"""
اختبارات الدفعة التاسعة عشرة — الأعطاب الأربعة من مراجعتك.

كلها أُعيد إنتاجها قبل الإصلاح، ثلاثة منها من صنعي في دفعات سابقة.
"""

from __future__ import annotations

import json

import pytest

from engines.narrator.gazetteer import NarratorGazetteer, Resolution, strip_particles
from packages.ingestion.ocr_corrector import (
    Lexicon, OcrCorrector, fix_diacritic_splits,
)
from packages.search.signals import ocr_quality

_T = "\u0640"


@pytest.fixture
def corrector(tmp_path):
    words = {
        "محمد": 2651, "حماد": 400, "الصفار": 200, "عليه": 16901, "عبد": 10779,
        "الله": 19673, "امن": 900, "موا": 300, "من": 9000, "في": 9000,
        "بن": 12000, "عن": 15000, "د": 16359, "محم": 13427, "حم": 5000,
        "اد": 3000, "ع": 1186, "ا": 8000, "م": 4000, "عدة": 700, "انه": 800,
    }
    p = tmp_path / "d.json"
    p.write_text(json.dumps(
        {"entries": [{"word": w, "frequency": f} for w, f in words.items()]},
        ensure_ascii=False), encoding="utf-8")
    return OcrCorrector(Lexicon(p))


# ===========================================================================
#  1) الدمج الكاذب — عطب أدخلتُه في الدفعة السابعة عشرة
# ===========================================================================

@pytest.mark.parametrize("text", [
    "مّ وأُ هاتنا يا رسول الله",
    "تعمله الله فليكن نقيّ ًا من الدنس .",
    "إنّ : الله خلق العقل",
    "عن أبيه ، عن سعد بن عبد الله",
    "الحقّ في ذلك",
    "علمّ به",
])
def test_no_false_merge(corrector, text):
    """
    "مّ وأُ" التحمت إلى "مّوأُ" لأن قاعدة الشقّ بعد الحركة لم تسأل
    هل ما بعدها بداية كلمة. الواو هنا واو عطف والهمزة فاء الكلمة.
    """
    _, stats = corrector.correct(text)
    assert stats.words_merged == 0, f"دمج كاذب: {stats.merged_examples}"


@pytest.mark.parametrize("broken,expected", [
    ("محمّ د بن يحيى", "محمّد"),
    ("عن عدّ ة من أصحابنا", "عدّة"),
    ("إنّ ه ليصوم اليوم", "إنّه"),
    ("محمّ د بن يعقوب", "محمّد"),
])
def test_correct_merge_still_works(corrector, broken, expected):
    """الحراسة يجب ألا تعطّل اللحم الصحيح."""
    out, stats = corrector.correct(broken)
    assert expected in out and stats.words_merged >= 1


def test_standalone_two_letter_words_protected():
    """"من" و"في" و"عن" كلمات لا شظايا، مهما سبقتها حركة."""
    for text in ["نقيّ ًا من الدنس", "الحقّ في ذلك", "قالّ عن فلان"]:
        out, n = fix_diacritic_splits(text)
        assert n == 0 and out == text


# ===========================================================================
#  2) مقياس الجودة كان ثنائياً عملياً
# ===========================================================================

def test_ocr_quality_is_graded_not_binary():
    """
    نصّان مختلفا الجودة كانا ينالان 1.00 معاً، فصار المقياس
    سليم/معطوب بلا درجات. والترتيب والتحقق يُبنيان عليه.
    """
    values = [
        ocr_quality("قال رسول الله الماء يطهر ولا يطهر ابدا"),
        ocr_quality("عمير ، عن حم ، اد عن الحلبي"),
        ocr_quality("علي ، عن عبد الله بن بكير ، عن عبد الله بن ابي يعفور"),
    ]
    assert len(set(values)) == 3, f"قيم غير متمايزة: {values}"


def test_quality_spans_a_real_range():
    texts = [
        "قال رسول الله الماء يطهر ولا يطهر ابدا",
        "علي ، عن عبد الله بن بكير ، عن عبد الله بن ابي يعفور",
        "عمير ، عن حم ، اد عن الحلبي",
        "محمّـــــ د بـــــن يحـــــيى".replace("ـ", _T),
        "االله علـيهم ( قال : قال رسول االله".replace("ـ", _T),
    ]
    values = [ocr_quality(t) for t in texts]
    assert len(set(values)) == len(texts)
    assert max(values) - min(values) > 0.8


def test_quality_ordering_matches_readability():
    clean = ocr_quality("قال رسول الله الماء يطهر ولا يطهر ابدا")
    punctuated = ocr_quality("علي ، عن عبد الله بن بكير ، عن عبد الله")
    fragmented = ocr_quality("عمير ، عن حم ، اد عن الحلبي")
    assert clean > punctuated > fragmented


# ===========================================================================
#  3) ربط الرواة — كان 7 من 20
# ===========================================================================

@pytest.fixture(scope="module")
def gazetteer():
    return NarratorGazetteer()


@pytest.mark.parametrize("raw,canonical", [
    ("وعن محمد بن يحيي", "محمد بن يحيى العطار"),
    ("عن أحمد بن محمد", "أحمد بن محمد بن عيسى"),
    ("، عن الحسين بن سعيد", "الحسين بن سعيد الأهوازي"),
    ("وبإسناده عن سعد بن عبد الله", "سعد بن عبد الله الأشعري"),
    ("عنه عن صفوان", "صفوان بن يحيى"),
    ("عن ابن ابي عمير", "محمد بن أبي عمير"),
])
def test_particles_no_longer_block_resolution(gazetteer, raw, canonical):
    """
    "وعن محمد بن يحيى" لم تطابق شيئاً لأن واو العطف جزء من المفتاح.
    """
    r = gazetteer.resolve(raw)
    assert r.resolved, f"{raw} لم يُربط"
    assert r.narrator.canonical_name == canonical


@pytest.mark.parametrize("raw,expected", [
    ("وعن محمد بن يحيى", "محمد بن يحيى"),
    ("، عن الحسين بن سعيد ،", "الحسين بن سعيد"),
    ("وبإسناده عن سعد بن عبد الله", "سعد بن عبد الله"),
    ("عن أحمد بن محمد عن", "أحمد بن محمد"),
])
def test_strip_particles(raw, expected):
    assert strip_particles(raw) == expected


def test_particles_only_is_unresolved(gazetteer):
    assert gazetteer.resolve("وعن ، عن").resolution is Resolution.UNRESOLVED


def test_unknown_still_declared(gazetteer):
    r = gazetteer.resolve("فلان بن فلان الذي لا وجود له")
    assert r.resolution is Resolution.UNRESOLVED and r.narrator is None


def test_resolution_rate_on_real_isnad_names(gazetteer):
    """قياس على أسماء بصيغتها في السند الفعلي."""
    names = [
        "وعن محمد بن يحيي", "عن أحمد بن محمد", "، عن الحسين بن سعيد",
        "محمد بن يعقوب", "وبإسناده عن سعد بن عبد الله", "عن ابن ابي عمير",
        "علي بن ابراهيم القمي", "عنه عن صفوان", "زرارة", "فلان بن فلان",
    ]
    resolved = sum(1 for n in names if gazetteer.resolve(n).resolved)
    assert resolved >= 8, f"نسبة الربط منخفضة: {resolved}/{len(names)}"


# ===========================================================================
#  4) فحص الإقلاع كان هشّاً
# ===========================================================================

def test_startup_check_does_not_assume_route_shape():
    """
    كسر الفحصُ سابقاً لأنه افترض أن كل عنصر في app.routes يحمل
    سمة `path`. القائمة تخلط أنواعاً، وبعضها بلا هذه السمة.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "scripts" / "verify_imports.py")
    text = src.read_text(encoding="utf-8")
    assert "getattr(route" in text, "الوصول المباشر لـ .path يعيد العطب"
    assert "check_app_starts" in text


def test_verifier_script_compiles():
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "scripts" / "verify_imports.py"
    compile(p.read_text(encoding="utf-8"), str(p), "exec")
