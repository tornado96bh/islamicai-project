"""اختبارات محرك التخطيط — كل الحالات من متن المستخدم الفعلي."""

from __future__ import annotations

import pytest

from packages.layout.classifier import (
    LayoutClassifier,
    LayoutType,
    layout_bonus,
)


@pytest.fixture
def clf():
    return LayoutClassifier()


# --- الهوامش: مصدر الكيانات المزعجة ------------------------------------

@pytest.mark.parametrize("text", [
    ")١ ( يأتي في الحديث ٠١ من الباب ٠٢ من أبواب أحكام المساكن .",
    ")١ ( في المصدر » : عبد االله « .",
    ")١ ( في نسخة عبد االله .",
    ")٢ ( يأ تي في الحديث ٦١ ، ٩ ، ٥ ، ١ من الباب ٦٢",
])
def test_footnotes_detected(clf, text):
    assert clf.classify(text).layout_type is LayoutType.FOOTNOTE


def test_footnote_without_marker_by_content(clf):
    v = clf.classify("٤ الكافي ، ٦ / ٤٥ : ٣ ويأتي في الحديث ١ من الباب ٤")
    assert v.layout_type is LayoutType.FOOTNOTE


# --- الترويسة والعناوين -------------------------------------------------

@pytest.mark.parametrize("text", [
    "٨٩٢ كتاب الطهارة أبواب نواقض الوضوء",
    "٠٣٣ كتاب الطهارة أبواب احكام الخلوة",
])
def test_running_head(clf, text):
    assert clf.classify(text).layout_type is LayoutType.RUNNING_HEAD


def test_numbered_chapter_heading(clf):
    v = clf.classify("٧١ ـ باب كراهة الاستنجاء بيد فيها خاتم عليه اسم ، االله")
    assert v.layout_type is LayoutType.HEADING


def test_bare_page_number(clf):
    assert clf.classify("٣٣٢").layout_type is LayoutType.PAGE_NUMBER


# --- السند ---------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "] ٧٦٨ ١ [ محمّ د بن يعقوب ، عن عدّ ة من أصحابنا ، عن أحمد بن محمّ ، د",
    "] ٨٢٤ [ ٧ وعن المفيد ، عن ابن قولويه ، عن أبيه ، عن سعد بن عبد الله ،",
    "وبإسناده عن أحمد بن محم ، د عن علي بن الحكم )٢( .",
    "محمّ د بن خالد ، عن عبد االله بن بكير قال : قلت لأبي عبد االله",
])
def test_sanad_detected(clf, text):
    assert clf.classify(text).layout_type is LayoutType.SANAD


# --- التخريج -------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "ورواه الشيخ بإسناده عن سعد بن عبد الله ، عن الحسن بن علي ، عن",
    "ورواه الصدوق في ) العلل ( عن أبيه ، عن سعد بن عبد الله ، عن",
    "وحديث عمار الساباطي ، عن أبي عبد االله ) عليه السلام ( ، مثله )١( .",
])
def test_takhrij_detected(clf, text):
    assert clf.classify(text).layout_type is LayoutType.TAKHRIJ


# --- المتن ---------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "قال رسول االله ) صلى االله عليه وآله ( : الماء يطهر ولا يطهر .",
    "قال رسول االله ) صلى االله عليه وآله ( : ثلاث منجيات : خوف االله في السرّ",
    "وبارز االله بما كرهه ، لقي االله وهو ماقت له .",
    "ردّ عليك هذا الأمر فهو كالرادّ على رسول االله وعلى االله عز وجل .",
])
def test_matn_detected(clf, text):
    assert clf.classify(text).layout_type is LayoutType.MATN


# --- التحفّظ والتفسير ----------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_is_unknown(clf, value):
    v = clf.classify(value)
    assert v.layout_type is LayoutType.UNKNOWN
    assert v.confidence == 0.0


def test_every_verdict_has_reasons(clf):
    for text in [")١ ( في المصدر", "٨٩٢ كتاب الطهارة أبواب", "قال رسول االله : كذا وكذا"]:
        assert clf.classify(text).reasons


def test_high_threshold_prefers_unknown_over_guessing(clf):
    """رفع العتبة يجب أن يزيد UNKNOWN لا أن يغيّر التصنيفات القاطعة."""
    strict = LayoutClassifier(min_confidence=0.9)
    weak = "وبارز االله بما كرهه ، لقي االله وهو ماقت له ."
    assert clf.classify(weak).layout_type is LayoutType.MATN
    assert strict.classify(weak).layout_type is LayoutType.UNKNOWN
    # القاطع لا يتأثر
    assert strict.classify(")١ ( في المصدر").layout_type is LayoutType.FOOTNOTE


def test_confidence_in_range(clf):
    for text in [")١ ( x", "٣٣٢", "قال رسول االله : كذا", "محمد بن خالد ، عن علي"]:
        assert 0.0 <= clf.classify(text).confidence <= 1.0


def test_classification_is_deterministic(clf):
    text = "] ٧٦٨ ١ [ محمّ د بن يعقوب ، عن عدّ ة من أصحابنا"
    assert clf.classify(text).layout_type is clf.classify(text).layout_type


# --- أوزان الترتيب -------------------------------------------------------

def test_matn_outranks_footnote():
    assert layout_bonus("matn") > layout_bonus("footnote")
    assert layout_bonus("footnote") > layout_bonus("running_head")


def test_bonus_stays_in_rrf_scale():
    """درس الدفعة الثالثة: أي إشارة تتجاوز حجم RRF تبتلع الترتيب."""
    for t in LayoutType:
        assert abs(layout_bonus(t)) <= 0.02


def test_unknown_layout_is_neutral():
    assert layout_bonus("unknown") == 0.0
    assert layout_bonus(None) == 0.0
    assert layout_bonus("nonsense") == 0.0
