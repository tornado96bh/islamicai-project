"""اختبارات الإشارات 1.1.0 — إصلاح مكافأة القِصَر."""

from __future__ import annotations

import pytest

from packages.search.signals import (
    DEFAULT_WEIGHTS,
    compute_signals,
    informativeness,
    length_prior,
    looks_like_index_line,
)

_T = "\u0640"


def _score(raw: str, norm: str, q=("الله",)) -> float:
    return compute_signals(
        raw_text=raw, normalized_text=norm, query_tokens=list(q)
    ).weighted(DEFAULT_WEIGHTS)


# --- العطب الأصلي: مكافأة القِصَر -----------------------------------------

def test_ocr_quality_is_a_penalty_not_a_reward():
    """
    النص القصير النظيف كان ينال 1.00 فيتفوّق على الفقرة المفيدة.
    الآن الجودة تُطرح عند السوء ولا تُضاف عند الحسن.
    """
    short_clean = _score("بتقوى الله والورع .", "بتقوي الله والورع .")
    long_useful = _score(
        "الله به الجنة وإنه ليصوم اليوم تطوعا يريد به وجه الله فيدخله الله به الجنة .",
        "الله به الجنه وانه ليصوم اليوم تطوعا يريد به وجه الله فيدخله الله به الجنه .",
    )
    assert long_useful > short_clean


def test_signals_no_longer_cancel_the_base():
    """
    الارتباط بـ rrf_base كان −0.93، فكانت الإشارات تُلغيه.
    الاختبار: النص المفيد الطويل لا يجوز أن ينال أقل من القصير النمطي.
    """
    boilerplate = _score("ذلك إن شاء الله تعالى .", "ذلك ان شا الله تعالي .")
    substantive = _score(
        "قال رسول الله صلى الله عليه وآله ثلاث منجيات خوف الله في السر والعلانية .",
        "قال رسول الله صلي الله عليه واله ثلاث منجيات خوف الله في السر والعلانيه .",
    )
    assert substantive > boilerplate


# --- سابقة الطول ----------------------------------------------------------

@pytest.mark.parametrize("n,expected", [(0, 0.0), (3, 0.0), (12, 1.0), (25, 1.0)])
def test_length_prior_values(n, expected):
    assert length_prior(n) == expected


def test_length_prior_is_monotonic_in_the_useful_range():
    values = [length_prior(n) for n in range(4, 12)]
    assert values == sorted(values)


def test_very_long_text_slightly_reduced():
    assert length_prior(90) < length_prior(20)


# --- الإفادة --------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "ذلك ان شا الله تعالي .",
    "الحمد الله رب العالمين .",
    "النجاسات ان شا الله )1(",
])
def test_boilerplate_scores_low(text):
    assert informativeness(text) < 0.75


def test_substantive_text_scores_high():
    assert informativeness("الما يطهر ولا يطهر الا ما غير لونه او طعمه") == 1.0


@pytest.mark.parametrize("value", ["", "   "])
def test_informativeness_empty(value):
    assert informativeness(value) == 0.0


# --- سطور الفهارس ---------------------------------------------------------

def test_index_line_detected():
    assert looks_like_index_line("اسم الله . . . ....................... 01 768 678 033")


def test_normal_text_not_flagged_as_index():
    assert not looks_like_index_line("قال رسول الله صلي الله عليه واله : الما يطهر .")


def test_index_line_is_demoted():
    index_line = _score(
        "اسم االله . . . ....................... ٠١ ٧٦٨ ٦٧٨",
        "اسم الله . . . ....................... 01 768 678",
    )
    normal = _score(
        "قال رسول الله صلي الله عليه واله الما يطهر ولا يطهر ابدا .",
        "قال رسول الله صلي الله عليه واله الما يطهر ولا يطهر ابدا .",
    )
    assert normal > index_line


# --- الحراسة العامة -------------------------------------------------------

def test_damaged_long_text_still_penalised():
    damaged = _score(
        ("علـي ، عــن عبـد االله بــن بكـير ، عــن عبــد االله بـن أبي يعفــور").replace("ـ", _T * 3),
        "علي ، عن عبد الله بن بكير ، عن عبد الله بن ابي يعفور",
    )
    clean = _score(
        "علي ، عن عبد الله بن بكير ، عن عبد الله بن ابي يعفور",
        "علي ، عن عبد الله بن بكير ، عن عبد الله بن ابي يعفور",
    )
    assert clean > damaged


def test_total_weight_stays_in_rrf_scale():
    """درس الدفعة الثالثة، ما زال سارياً."""
    bonuses = sum(v for k, v in DEFAULT_WEIGHTS.items() if k != "ocr_penalty")
    assert bonuses <= 0.035
    assert DEFAULT_WEIGHTS["ocr_penalty"] <= 0.02


def test_all_signals_reported():
    d = compute_signals(
        raw_text="نص", normalized_text="نص", query_tokens=["نص"]
    ).as_dict()
    for key in (
        "sig_ocr_quality", "sig_coverage", "sig_completeness",
        "sig_density", "sig_length_prior", "sig_informativeness",
    ):
        assert key in d


def test_real_results_spread_widened():
    """
    على نتائجك الفعلية: المدى كان 0.00505 بعد النسخة السابقة.
    هذا الاختبار يضمن ألا يعود الانكماش.
    """
    rows = [
        ("الله به الجن وان ه ليصوم اليوم تطوعا يريد به وجه الله فيدخله الله به الجنه .",) * 2,
        ("درهم ودينار وعليه اسم الله",) * 2,
        ("ذلك ان شا الله تعالي .",) * 2,
        ("النجاسات ان شا الله )1(",) * 2,
    ]
    scores = [_score(a, b) for a, b in rows]
    assert max(scores) - min(scores) > 0.006
