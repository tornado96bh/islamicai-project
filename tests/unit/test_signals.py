"""
اختبارات الإشارات — محدَّثة لتصميم 1.1.0.

سبب التحديث: هذا الملف كُتب للنسخة 1.0.0 حيث كانت جودة OCR **مكافأة**.
بعد تحويلها إلى **عقوبة** في 1.1.0 صار توكيدان فيه يناقضان التصميم:

  1. test_total_weight_stays_in_rrf_scale جمع ocr_penalty مع المكافآت،
     وهو يُطرح لا يُضاف، فالمجموع لا معنى له.
  2. test_signals_discriminate اختار أربعة نصوص أحدها قصير نظيف
     ("درهم ودينار") كانت 1.0.0 ترفعه إلى القمة. بعد إصلاح مكافأة
     القِصَر انكمش مدى تلك الأربعة تحديداً — وهو المقصود.

اختبار فاشل متوقَّع أسوأ من عدمه: يُفقد الثقة في بقية المجموعة.
"""

from __future__ import annotations

import pytest

from packages.search.signals import (
    DEFAULT_WEIGHTS,
    compute_signals,
    completeness,
    ocr_quality,
    query_coverage,
    term_density,
)

_T = "\u0640"


def _score(raw: str, norm: str, q=("الله",)) -> float:
    return compute_signals(
        raw_text=raw, normalized_text=norm, query_tokens=list(q)
    ).weighted(DEFAULT_WEIGHTS)


# --- جودة OCR -------------------------------------------------------------

def test_clean_text_scores_high():
    assert ocr_quality("قال رسول الله صلى الله عليه وآله الماء يطهر ولا يطهر") > 0.85


def test_stretched_text_scores_low():
    assert ocr_quality("قــــــال رســــــول االله".replace("ــ", _T * 4)) < 0.6


def test_fragmented_text_scores_low():
    assert ocr_quality("عمير ، عن حم ، اد عن الحلبي ، عن ابي") < 0.6


def test_ocr_quality_is_graded_not_binary():
    values = [
        ocr_quality("قال رسول الله الماء يطهر ولا يطهر ابدا"),
        ocr_quality("عمير ، عن حم ، اد عن الحلبي"),
        ocr_quality("علي ، عن عبد الله بن بكير ، عن عبد الله بن ابي يعفور"),
    ]
    assert len(set(values)) == 3
    assert all(0.0 <= v <= 1.0 for v in values)


@pytest.mark.parametrize("value", ["", "   "])
def test_ocr_quality_empty(value):
    assert ocr_quality(value) == 0.0


# --- تغطية الاستعلام ------------------------------------------------------

def test_coverage_is_a_ratio_not_a_flag():
    text = "قال رسول الله عليه السلام".split()
    assert query_coverage(["الله"], text) == 1.0
    assert query_coverage(["الله", "زراره"], text) == 0.5
    assert query_coverage(["زراره", "اعين"], text) == 0.0


def test_coverage_empty_query():
    assert query_coverage([], ["الله"]) == 0.0


# --- الاكتمال والكثافة ----------------------------------------------------

def test_complete_sentence_scores_higher_than_fragment():
    assert completeness(
        "قال رسول الله صلي الله عليه واله الماء يطهر ولا يطهر ."
    ) > completeness("، عن عبد الله بن بكير ، عن عبد")


def test_density_rewards_focus_over_passing_mention():
    assert term_density(["الله"], "الله الله عليه الله".split()) > term_density(
        ["الله"], ("كلمه " * 30 + "الله").split()
    )


# --- التمييز على نتائج حقيقية ---------------------------------------------

def test_signals_discriminate_between_real_results():
    """
    مجموعة ممثِّلة: متن مفيد، سند معطوب، عبارة نمطية، سطر قصير.
    المجموعة السابقة كانت أربعة نصوص أغلبها متشابه الطول.
    """
    rows = [
        ("االله به الجنّ وإنّ ه ليصوم اليوم تطوّ عاً يريد به وجه االله فيدخله االله به الجنة .",
         "الله به الجن وان ه ليصوم اليوم تطوعا يريد به وجه الله فيدخله الله به الجنه ."),
        ("علـي ، عــن عبـد االله بــن بكـير ، عــن عبــد االله بـن أبي يعفــور".replace("ـ", _T * 3),
         "علي ، عن عبد الله بن بكير ، عن عبد الله بن ابي يعفور"),
        ("ذلك إن شاء االله تعالى .", "ذلك ان شا الله تعالي ."),
        ("النجاسات إن شاء االله )١(", "النجاسات ان شا الله )1("),
    ]
    weighted = [_score(raw, norm) for raw, norm in rows]
    assert len(set(round(w, 5) for w in weighted)) == len(rows), "لا تمييز"
    assert max(weighted) - min(weighted) > 0.008, "المدى أضيق من أن يميّز"


def test_useful_passage_beats_boilerplate():
    """الاختبار الجوهري بعد إصلاح 1.1.0."""
    useful = _score(
        "االله به الجنّ وإنّ ه ليصوم اليوم تطوّ عاً يريد به وجه االله فيدخله االله به الجنة .",
        "الله به الجن وان ه ليصوم اليوم تطوعا يريد به وجه الله فيدخله الله به الجنه .",
    )
    boilerplate = _score("ذلك إن شاء االله تعالى .", "ذلك ان شا الله تعالي .")
    assert useful > boilerplate


def test_damaged_text_ranks_below_clean_text():
    clean = _score(
        "قال رسول الله صلي الله عليه واله الما يطهر ولا يطهر ابدا .",
        "قال رسول الله صلي الله عليه واله الما يطهر ولا يطهر ابدا .",
    )
    damaged = _score(
        "قال رســول االله صــلي االله عليــه والــه المــا يطهــر ولا يطهــر ابــدا .".replace("ـ", _T * 3),
        "قال رسول الله صلي الله عليه واله الما يطهر ولا يطهر ابدا .",
    )
    assert clean > damaged


# --- حدود الأوزان ----------------------------------------------------------

def test_bonus_weights_stay_in_rrf_scale():
    """
    ocr_penalty تُطرح لا تُضاف، فجمعها مع المكافآت بلا معنى.
    الحد يخص المكافآت وحدها، والعقوبة لها حدّها المستقل.
    """
    bonuses = sum(v for k, v in DEFAULT_WEIGHTS.items() if k != "ocr_penalty")
    assert bonuses <= 0.035, "المكافآت تجاوزت حجم أساس RRF"
    assert DEFAULT_WEIGHTS["ocr_penalty"] <= 0.02, "العقوبة أثقل من اللازم"


def test_penalty_cannot_zero_out_a_good_result():
    """العقوبة القصوى يجب ألا تُسقط نتيجة مكتملة إلى السالب."""
    worst = compute_signals(
        raw_text=_T * 200, normalized_text="", query_tokens=["الله"]
    ).weighted(DEFAULT_WEIGHTS)
    assert worst >= -DEFAULT_WEIGHTS["ocr_penalty"]


def test_all_signals_reported():
    d = compute_signals(
        raw_text="نص", normalized_text="نص", query_tokens=["نص"]
    ).as_dict()
    for key in (
        "sig_ocr_quality", "sig_coverage", "sig_completeness",
        "sig_density", "sig_length_prior", "sig_informativeness",
    ):
        assert key in d
