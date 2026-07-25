"""اختبارات إصلاحات محرك التخطيط 1.1.0 — كلها من عيّنة مراجعتك."""

from __future__ import annotations

import pytest

from packages.layout.classifier import LayoutClassifier, LayoutType


@pytest.fixture
def clf():
    return LayoutClassifier()


# --- الإصلاح 1: إحالة مصدر مرقَّمة بلا قوسين -------------------------

@pytest.mark.parametrize("text", [
    "٠١ ـ الزهد / ٢٧ : ٢٩١ .",
    "٧ ـ الفقيه . ١١ / ٨ : ١",
    "٥ ـ التهذيب : ١ ٥٣٢ / ٩٧٦",
    "٨ ـ التهذيب : ١ ٢١٤ / ٨٩٢١",
])
def test_numbered_source_citation_is_footnote(clf, text):
    """كانت تُصنَّف متناً لأن الاحتياطي النثري يبتلعها."""
    assert clf.classify(text).layout_type is LayoutType.FOOTNOTE


def test_source_citation_rule_is_structural_not_a_booklist():
    """القاعدة بنيوية فتعمّ على مصادر لم تُذكر في أي قائمة."""
    clf = LayoutClassifier()
    assert clf.classify("٣ ـ مصدر لم يذكر قط / ١٢ : ٤٥").layout_type is LayoutType.FOOTNOTE


# --- الإصلاح 2: عنوان كتاب أو قسم ------------------------------------

@pytest.mark.parametrize("text", [
    "ُكتاب الم ضارب ة .",   # يبدأ بضمّة — لهذا يُطابَق على المطبّع
    "كتاب الطهارة",
    "أبواب نواقض الوضوء",
])
def test_section_title_is_heading(clf, text):
    assert clf.classify(text).layout_type is LayoutType.HEADING


def test_long_text_starting_with_kitab_is_not_a_heading(clf):
    """العنوان قصير؛ الجملة الطويلة التي تبدأ بـ كتاب ليست عنواناً."""
    long_text = "كتاب الطهارة فيه أبواب كثيرة ومسائل متشعبة يطول شرحها جداً هنا"
    assert clf.classify(long_text).layout_type is not LayoutType.HEADING


# --- الإصلاح 3: سلسلة الإسناد بلا صيغة افتتاح ------------------------

@pytest.mark.parametrize("text", [
    "الســعدآبادي ، عــن احمــد بــن أبي عبــد االله البرقــي ، عــن أبيــه",
    "، دمحمّ عن الحسين بن سعيد وأبيه محمّ د بن عيسى ، عن محمّ د",
    "عن محمد بن سنان ، عن المفضّ ل بن عمر ، عن أبي عبد الله",
])
def test_isnad_chain_without_opener(clf, text):
    """كانت unknown لأن الوزن كان مبنياً على صيغة الافتتاح وحدها."""
    assert clf.classify(text).layout_type is LayoutType.SANAD


# --- الإصلاح 4: كثافة الأرقام تمنع الاحتياطي النثري ------------------

def test_digit_heavy_line_is_not_matn_by_fallback(clf):
    assert clf.classify("١ ٢٢ / ٣٤ : ٥٦ ، ٧٨ / ٩٠ : ١٢").layout_type is not LayoutType.MATN


# --- حراسة: لا انحدار في ما كان يعمل ---------------------------------

@pytest.mark.parametrize("text,expected", [
    (")١ ( في المصدر » : عبد االله « .", LayoutType.FOOTNOTE),
    ("٨٩٢ كتاب الطهارة أبواب نواقض الوضوء", LayoutType.RUNNING_HEAD),
    ("٢٢ ـ باب وجوب كون مسح الرأس على مقدّ . مه", LayoutType.HEADING),
    ("قال رسول االله ) صلى االله عليه وآله ( : الماء يطهر ولا يطهر .", LayoutType.MATN),
    ("وبارز االله بما كرهه ، لقي االله وهو ماقت له .", LayoutType.MATN),
    ("] ٧٦٨ ١ [ محمّ د بن يعقوب ، عن عدّ ة من أصحابنا", LayoutType.SANAD),
    ("ورواه الشيخ بإسناده عن سعد بن عبد الله ، عن الحسن بن علي", LayoutType.TAKHRIJ),
    ("٣٣٢", LayoutType.PAGE_NUMBER),
])
def test_no_regression(clf, text, expected):
    assert clf.classify(text).layout_type is expected


def test_running_head_still_beats_section_title(clf):
    """"٨٩٢ كتاب الطهارة" ترويسة لا عنوان — الرقم السابق يحسم."""
    assert clf.classify("٨٩٢ كتاب الطهارة أبواب").layout_type is LayoutType.RUNNING_HEAD
