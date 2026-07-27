"""اختبارات الدفعة السابعة — لحم الكلمة عبر علامة الترقيم."""

from __future__ import annotations

import json

import pytest

from packages.ingestion.ocr_corrector import Lexicon, OcrCorrector


@pytest.fixture
def lexicon(tmp_path):
    words = {
        "محمد": 2651, "حماد": 400, "الصفار": 200, "عليه": 16901,
        "عبد": 10779, "الله": 19673, "الحسن": 900,
        # شظايا ملوّثة: موجودة بترددات عالية كما في المعجم الحقيقي
        "د": 16359, "محم": 13427, "حم": 5000, "اد": 3000,
        "ع": 1186, "من": 9000, "في": 9000, "بن": 12000, "عن": 15000,
    }
    p = tmp_path / "dictionary.json"
    p.write_text(json.dumps(
        {"entries": [{"word": w, "frequency": f} for w, f in words.items()]},
        ensure_ascii=False), encoding="utf-8")
    return Lexicon(p)


@pytest.fixture
def corrector(lexicon):
    return OcrCorrector(lexicon)


# --- العطب الأشيع: ترقيم داخل الكلمة ------------------------------------

@pytest.mark.parametrize("broken,expected", [
    ("عن أحمد بن محمّ ، د عن علي", "محمّد"),
    ("عن حمّ ، اد عن حريز", "حمّاد"),
    ("عن الصفّ ، ار عن", "الصفّار"),
])
def test_merge_across_punctuation(corrector, broken, expected):
    """
    "محمّ ، د" هو سبب بقاء أسماء الرواة مقطّعة: الفاصلة تفصل الشظيتين
    فلا تراهما دالة الجوار العادية.
    """
    out, stats = corrector.correct(broken)
    assert expected in out
    assert stats.words_merged >= 1


def test_merge_still_works_without_punctuation(corrector):
    out, stats = corrector.correct("محمّ د بن يعقوب")
    assert "محمّد" in out and stats.words_merged >= 1


# --- الحراسة: لا لحم عبر حدود جملة حقيقية -------------------------------

@pytest.mark.parametrize("text", [
    "قال رسول الله ، الماء يطهر ولا يطهر",
    "عن أبي عبد الله ) عليه السلام ( ، مثله",
    "في الحديث ١ ، من الباب ٤",
    "عن أبيه ، عن سعد بن عبد الله",
])
def test_no_merge_across_real_sentence_breaks(corrector, text):
    _, stats = corrector.correct(text)
    assert stats.words_merged == 0


def test_protected_words_never_merged_even_relaxed(corrector):
    """"عن" و"من" و"بن" محمية على الجانبين حتى مع التخفيف."""
    for text in ["الحسن ، عن سعيد", "الباب ، من أبواب", "أحمد ، بن محمد"]:
        _, stats = corrector.correct(text)
        assert stats.words_merged == 0, text


def test_digits_never_merged_across_punctuation(corrector):
    out, stats = corrector.correct("الحديث ١ ، ٢ من الباب")
    assert stats.words_merged == 0
    assert "١ ، ٢" in out


def test_unknown_join_is_not_merged(corrector):
    """الاجتماع الذي لا ينتج كلمة معروفة يُترك كما هو."""
    _, stats = corrector.correct("زقط ، خبل")
    assert stats.words_merged == 0


# --- الشفافية -------------------------------------------------------------

def test_merges_are_reported(corrector):
    _, stats = corrector.correct("عن أحمد بن محمّ ، د")
    assert stats.merged_examples
    assert any("محمّد" == b for _, b in stats.merged_examples)


def test_corrector_is_idempotent(corrector):
    once, _ = corrector.correct("عن أحمد بن محمّ ، د عن حمّ ، اد")
    twice, stats2 = corrector.correct(once)
    assert once == twice and stats2.words_merged == 0


@pytest.mark.parametrize("value", [None, "", "   ", "،", "، ، ،"])
def test_edge_inputs(corrector, value):
    out, stats = corrector.correct(value)
    assert stats.words_merged == 0
