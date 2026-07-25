"""اختبارات ربط فلتر الكيانات — الحالات من مخرجاتك الفعلية."""

from __future__ import annotations

import pytest

from packages.learning.entity_filter import EntityKind, classify_entity


@pytest.mark.parametrize("label", ["من الباب", "في الحديث"])
def test_footnote_phrases_rejected(label):
    """
    هاتان تكررتا 6552 و4608 مرة، وكل أمثلتهما تبدأ بـ ")١ (" أي هوامش.
    التكرار وحده لا يصنع كياناً.
    """
    assert not classify_entity(label).accepted


@pytest.mark.parametrize("label,cleaned", [
    ("عن أحمد بن محم د", "أحمد بن محم د"),
    ("عن سعد بن عبد الله", "سعد بن عبد الله"),
])
def test_transmission_prefix_stripped(label, cleaned):
    v = classify_entity(label)
    assert v.accepted and v.kind is EntityKind.PERSON
    assert v.cleaned_label == cleaned


def test_book_not_labelled_person():
    v = classify_entity("كتاب الطهارة")
    assert v.accepted and v.kind is EntityKind.BOOK


def test_prophet_title_accepted():
    assert classify_entity("النبي صلى الله عليه وآله").accepted


def test_every_verdict_carries_a_reason():
    for label in ["من الباب", "أحمد بن محمد", "كتاب الطهارة", ""]:
        assert classify_entity(label).reason
