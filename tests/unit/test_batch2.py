"""اختبارات الدفعة الثانية: مصحح OCR، دمج RRF، فلتر الكيانات."""

from __future__ import annotations

import json

import pytest

from packages.ingestion.ocr_corrector import (
    Lexicon,
    OcrCorrector,
    fix_ligatures,
    remove_stretch,
)
from packages.learning.entity_filter import EntityKind, classify_entity, filter_entities
from packages.search.fusion import (
    exact_form_boost,
    length_penalty,
    reciprocal_rank_fusion,
)


# ===========================================================================
#  معجم اختبار — لا يعتمد على وجود storage/
# ===========================================================================

@pytest.fixture
def lexicon(tmp_path):
    words = {
        "عليه": 16901, "عبد": 10779, "محمد": 2651, "الحسن": 900,
        "الله": 19673, "قال": 16955, "السلام": 12789, "الطهاره": 500,
        "د": 16359, "محم": 13427, "ع": 1186, "من": 9000, "في": 9000,
        "الباب": 13032, "الحديث": 8000, "بن": 12000,
    }
    p = tmp_path / "dictionary.json"
    p.write_text(
        json.dumps({"entries": [{"word": w, "frequency": f} for w, f in words.items()]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    return Lexicon(p)


@pytest.fixture
def corrector(lexicon):
    return OcrCorrector(lexicon)


# ===========================================================================
#  1) مصحح OCR
# ===========================================================================

def test_stretch_removed():
    out, n = remove_stretch("عــــــــــن وهــــــــــب")
    assert out == "عن وهب"
    assert n == 2


def test_stretch_noop_when_absent():
    out, n = remove_stretch("عن وهب")
    assert out == "عن وهب" and n == 0


def test_ligature_allah():
    out, n = fix_ligatures("قال االله تعالى")
    assert out == "قال الله تعالى" and n == 1


def test_ligature_only_whole_token():
    """لا يُستبدل جزء من كلمة أطول."""
    out, n = fix_ligatures("بااللهم")
    assert out == "بااللهم" and n == 0


@pytest.mark.parametrize(
    "broken,expected_fragment",
    [
        ("ع ليه", "عليه"),
        ("ع بد", "عبد"),
        ("محم د", "محمد"),
        ("ا لحسن", "الحسن"),
    ],
)
def test_intra_word_split_repaired(corrector, broken, expected_fragment):
    out, stats = corrector.correct(broken)
    assert expected_fragment in out
    assert stats.words_merged >= 1


@pytest.mark.parametrize(
    "text",
    [
        "من الباب",
        "في الحديث",
        "عن أبي عبد الله عليه السلام",
        "قال رسول الله صلى الله عليه وآله",
    ],
)
def test_valid_phrases_never_merged(corrector, text):
    """الكلمات المحمية تمنع دمج العبارات السليمة."""
    _, stats = corrector.correct(text)
    assert stats.words_merged == 0


def test_digits_never_merged(corrector):
    """الحالة الخطرة: "١ من" يجب ألا تصير "١من"."""
    out, stats = corrector.correct("في الحديث ١ من الباب ٤")
    assert "١ من" in out
    assert stats.words_merged == 0


def test_punctuation_not_merged(corrector):
    out, stats = corrector.correct("عبد ( الله )")
    assert stats.words_merged == 0


def test_corrector_without_lexicon_is_safe():
    """بلا معجم، يعمل المصحح بأمان ولا يدمج شيئاً."""
    c = OcrCorrector(Lexicon())
    out, stats = c.correct("ع ليه السلام")
    assert stats.words_merged == 0
    assert out == "ع ليه السلام"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_corrector_empty_inputs(corrector, value):
    out, stats = corrector.correct(value)
    assert out == "" and stats.total() == 0


def test_stats_are_reported(corrector):
    """كل تغيير يجب أن يكون مفسَّراً (الماستر §9)."""
    _, stats = corrector.correct("عــــن ع ليه االله")
    assert stats.stretch_removed >= 1
    assert stats.ligatures_fixed >= 1
    assert stats.merged_examples


# ===========================================================================
#  2) دمج RRF
# ===========================================================================

def _hit(i, text="نص طويل بما يكفي للاختبار"):
    return {"id": i, "text": text}


def test_rrf_prefers_agreement_across_sources():
    """المستند الذي يظهر في محركين يتقدّم على من يظهر في واحد."""
    runs = {
        "fts": [_hit(1), _hit(2), _hit(3)],
        "fuzzy": [_hit(3), _hit(4), _hit(5)],
    }
    fused = reciprocal_rank_fusion(runs, key_fn=lambda h: str(h["id"]))
    assert fused[0].key == "3"


def test_rrf_ignores_duplicate_within_same_run():
    """
    جوهر إصلاح الانحدار: تكرار نفس العنصر داخل محرك واحد لا يراكم درجة.
    هذا ما جعل شظية من حرفين تتصدّر النتائج.
    """
    spam = [_hit(1)] * 8 + [_hit(2)]
    runs = {"fuzzy": spam}
    fused = reciprocal_rank_fusion(runs, key_fn=lambda h: str(h["id"]))
    assert len(fused) == 2
    assert len(fused[0].contributions) == 1


def test_rrf_contribution_is_bounded():
    """مساهمة أي محرك محدودة مهما كان مقياسه الخام."""
    runs = {"fuzzy": [_hit(1)]}
    fused = reciprocal_rank_fusion(runs, key_fn=lambda h: str(h["id"]), k=60)
    assert fused[0].score < 0.02


def test_rrf_empty_runs():
    assert reciprocal_rank_fusion({}, key_fn=lambda h: str(h["id"])) == []


def test_rrf_explains_itself():
    runs = {"fts": [_hit(1)], "fuzzy": [_hit(1)]}
    fused = reciprocal_rank_fusion(runs, key_fn=lambda h: str(h["id"]))
    explanation = fused[0].explain()
    assert "fts" in explanation and "fuzzy" in explanation


def test_length_penalty_demotes_fragments():
    runs = {"fuzzy": [_hit(1, ". الله"), _hit(2, "قال رسول الله صلى الله عليه وآله")]}
    fused = reciprocal_rank_fusion(runs, key_fn=lambda h: str(h["id"]))
    assert fused[0].key == "1"  # الشظية أولاً قبل الخفض
    after = length_penalty(fused, text_fn=lambda p: p["text"])
    assert after[0].key == "2"  # النص الكامل بعده


def test_exact_form_boost_solves_zurara():
    """
    مشكلة زرارة: من طابق الصورة الأصلية يتقدّم على من طابق المطبّعة فقط.
    """
    runs = {
        "fuzzy": [
            {"id": 1, "raw": "زراره القميص", "norm": "زراره القميص"},
            {"id": 2, "raw": "زرارة بن أعين", "norm": "زراره بن اعين"},
        ]
    }
    fused = reciprocal_rank_fusion(runs, key_fn=lambda h: str(h["id"]))
    assert fused[0].key == "1"

    boosted = exact_form_boost(
        fused,
        query_raw="زرارة",
        query_normalized="زراره",
        raw_text_fn=lambda p: p["raw"],
        normalized_text_fn=lambda p: p["norm"],
    )
    assert boosted[0].key == "2", "المطابقة بالصورة الأصلية يجب أن تتقدّم"


# ===========================================================================
#  3) فلتر الكيانات
# ===========================================================================

@pytest.mark.parametrize("label", ["من الباب", "في الحديث", "من أبواب"])
def test_function_phrases_rejected(label):
    v = classify_entity(label)
    assert not v.accepted
    assert v.kind is EntityKind.REJECTED


@pytest.mark.parametrize(
    "label,expected_clean",
    [
        ("عن أحمد بن محمد", "أحمد بن محمد"),
        ("عن سعد بن عبد الله", "سعد بن عبد الله"),
        ("زرارة بن أعين", "زرارة بن أعين"),
    ],
)
def test_person_accepted_and_cleaned(label, expected_clean):
    v = classify_entity(label)
    assert v.accepted and v.kind is EntityKind.PERSON
    assert v.cleaned_label == expected_clean


def test_book_classified_as_book_not_person():
    v = classify_entity("كتاب الطهارة")
    assert v.accepted and v.kind is EntityKind.BOOK


def test_labels_with_digits_rejected():
    assert not classify_entity("الباب ٤ من أبواب").accepted


def test_overlong_label_rejected():
    assert not classify_entity("واحد اثنان ثلاثة أربعة خمسة ستة سبعة ثمانية").accepted


@pytest.mark.parametrize("value", ["", "   ", None])
def test_empty_labels_rejected(value):
    assert not classify_entity(value).accepted


def test_filter_keeps_rejected_with_reason():
    """لا حذف صامت — المرفوض يُحتفظ به مع سببه."""
    accepted, rejected = filter_entities(
        [{"label": "من الباب"}, {"label": "أحمد بن محمد"}]
    )
    assert len(accepted) == 1 and len(rejected) == 1
    assert rejected[0]["filter_reason"]
    assert accepted[0]["entity_kind"] == "person"


def test_filter_is_deterministic():
    items = [{"label": x} for x in ["من الباب", "أحمد بن محمد", "كتاب الطهارة"]]
    a1, r1 = filter_entities(items)
    a2, r2 = filter_entities(items)
    assert [x["label"] for x in a1] == [x["label"] for x in a2]
    assert [x["label"] for x in r1] == [x["label"] for x in r2]
