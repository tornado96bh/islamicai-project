"""اختبارات الدفعة الخامسة عشرة — الحركات والنية والسجلّ."""

from __future__ import annotations

import pytest

from packages.arabic.diacritics import (
    MatchStrength, analyse, has_diacritics, light_stem, match_phrase,
    match_words, to_canonical, to_retrieval,
)
from packages.engines.registry import (
    ENGINES, EngineNotReady, Status, require_engine, summary,
)
from packages.search.intent_v2 import detect_intent


# ===========================================================================
#  الحركات — جوهر الطلب
# ===========================================================================

def test_diacritics_distinguish_meaning():
    """عَلَم و عِلْم كلمتان مختلفتان، لا تُخلطان في المطابقة الحرفية."""
    assert match_words("عَلَم", "عَلَم").strength is MatchStrength.EXACT
    assert match_words("عَلَم", "عِلْم").strength is not MatchStrength.EXACT


def test_unvocalised_match_is_kept_but_ranked_lower():
    """
    النص المصدر قد يكون غير مشكول، فالمطابقة المنزوعة لا تُقصى
    بل تنزل درجةً.
    """
    r = match_words("عَلَم", "علم")
    assert r.strength is MatchStrength.UNVOCALISED
    assert 0 < r.weight < match_words("عَلَم", "عَلَم").weight


def test_orthographic_variants_unify_without_losing_diacritics():
    """مسؤول = مسئول، والحركات باقية."""
    r = match_words("مسؤول", "مسئول")
    assert r.strength is MatchStrength.CANONICAL
    assert "\u064e" in to_canonical("عَلَم")


@pytest.mark.parametrize("text,expected", [
    ("عَلَم", True), ("علم", False), ("قَالَ رَسُولُ", True), ("قال رسول", False),
])
def test_diacritic_detection(text, expected):
    """وجود الحركات في السؤال إعلانُ نية، فكشفه أساس اختيار الطبقة."""
    assert has_diacritics(text) is expected


def test_four_layers_are_distinct():
    f = analyse("الوُضُوء")
    assert "\u064f" in f.canonical, "canonical يحفظ الحركات"
    assert "\u064f" not in f.retrieval, "retrieval ينزعها"
    assert f.stem == "وضوء", "الجذع يقشّر أداة التعريف"


@pytest.mark.parametrize("word,stem", [
    ("الوضوء", "وضوء"), ("بالوضوء", "وضوء"), ("والوضوء", "وضوء"), ("وضوء", "وضوء"),
])
def test_stem_groups_derivations(word, stem):
    assert light_stem(word) == stem


def test_stem_does_not_over_strip():
    """حدّ البقاء أربعة أحرف يمنع "وضوء" -> "ضوء"."""
    assert light_stem("وضوء") == "وضوء"


def test_unrelated_words_do_not_match():
    assert match_words("الوضوء", "الصلاة").strength is MatchStrength.NONE


def test_phrase_match_rewards_diacritics():
    q = "قَالَ رَسُولُ اللَّه"
    assert match_phrase(q, "قَالَ رَسُولُ اللَّه").score > match_phrase(
        q, "قال رسول الله"
    ).score


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_inputs(value):
    assert to_canonical(value) == ""
    assert to_retrieval(value) == ""
    assert match_words(value, "شيء").strength is MatchStrength.NONE


def test_tatweel_removed_everywhere():
    stretched = "قــــال".replace("ـ", "\u0640")
    assert "\u0640" not in to_canonical(stretched)
    assert to_retrieval(stretched) == "قال"


# ===========================================================================
#  النية — من 0.55 ثابتة إلى ثقة محسوبة
# ===========================================================================

@pytest.mark.parametrize("query,label,floor", [
    ("زرارة بن أعين", "narrator", 0.85),
    ("محمد بن يعقوب الكليني", "narrator", 0.85),
    ("باب نواقض الوضوء", "chapter", 0.8),
    ("كتاب الطهارة", "chapter", 0.8),
    ("ما حكم الوضوء بماء البحر", "ruling", 0.75),
    ("وبإسناده عن الحسين بن سعيد عن حماد", "isnad", 0.8),
    ("قال رسول الله صلى الله عليه وآله", "hadith", 0.75),
    ("] 29214 [ ج 1 ص 45", "citation", 0.75),
])
def test_intent_is_confident_when_evidence_is_clear(query, label, floor):
    r = detect_intent(query)
    assert r.label == label
    assert r.confidence >= floor, f"{query}: {r.confidence}"


def test_single_common_word_gets_low_confidence():
    """
    "الله" لا نية واضحة له. الرقم المنخفض هنا **صدق** لا عجز:
    الادعاء بغيره كذبُ معايرة.
    """
    r = detect_intent("الله")
    assert r.label == "general"
    assert r.confidence < 0.5
    assert not r.is_confident
    assert r.hints, "يجب أن يقترح طلب التوضيح"


def test_confidence_is_explainable():
    """كل ثقة يجب أن تُسند إلى أدلة مسمّاة."""
    r = detect_intent("زرارة بن أعين")
    assert r.evidence
    assert all(e.name for e in r.evidence)
    assert "evidence" in r.as_dict()


def test_close_runner_up_reduces_confidence():
    r = detect_intent("زرارة بن أعين")
    assert r.runner_up is not None


def test_no_intent_claims_certainty():
    """لا مصنّف قواعد يستحق 0.99."""
    for q in ["زرارة بن أعين", "باب نواقض الوضوء", "ما حكم الوضوء"]:
        assert detect_intent(q).confidence <= 0.96


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_query_intent(value):
    r = detect_intent(value)
    assert r.label == "general" and r.confidence == 0.0


# ===========================================================================
#  سجلّ المحركات — الصدق البرمجي
# ===========================================================================

def test_ready_engines_are_requestable():
    for key in ("diacritics", "intent", "layout", "ranking"):
        assert require_engine(key).status in (Status.READY, Status.PARTIAL)


@pytest.mark.parametrize("key", ["verifier", "knowledge_graph", "cross_encoder"])
def test_unready_engines_fail_loudly(key):
    """
    النتيجة الصامتة من محرك ناقص أخطر من غيابه: تبدو صحيحة.
    """
    with pytest.raises(EngineNotReady) as exc:
        require_engine(key)
    assert str(exc.value)


def test_unknown_engine_raises():
    with pytest.raises(EngineNotReady):
        require_engine("لا_يوجد")


def test_every_engine_declares_a_layer():
    for e in ENGINES.values():
        assert isinstance(e.layer, int)
        if e.status in (Status.NEEDS_DATA, Status.NOT_STARTED, Status.CONTRACT_ONLY):
            assert e.blocked_by or e.note, f"{e.key}: بلا سبب معلن"


def test_summary_covers_all_engines():
    assert sum(summary().values()) == len(ENGINES)
