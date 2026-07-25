"""اختبارات الدفعة السادسة — تنظيف أسماء الكيانات."""

from __future__ import annotations

import pytest

from packages.learning.entity_filter import EntityKind, classify_entity


# --- قطع أدوات التحمّل من الذيل -----------------------------------------

@pytest.mark.parametrize("label,cleaned", [
    ("محم د بن يعقوب عن", "محم د بن يعقوب"),
    ("الحسين بن سعيد عن", "الحسين بن سعيد"),
    ("محم د بن يحيى عن", "محم د بن يحيى"),
    ("محم د بن علي بن", "محم د بن علي"),
])
def test_trailing_particles_stripped(label, cleaned):
    v = classify_entity(label)
    assert v.accepted and v.cleaned_label == cleaned


# --- تعارض "علي" و"على" بعد التطبيع -------------------------------------

@pytest.mark.parametrize("label,cleaned", [
    ("علي بن إبراهيم عن", "علي بن إبراهيم"),
    ("عن علي بن الحكم", "علي بن الحكم"),
    ("علي بن الحسين", "علي بن الحسين"),
])
def test_ali_is_never_stripped_as_a_preposition(label, cleaned):
    """
    التطبيع يوحّد "على" حرف الجر مع "علي" الاسم. إدراج "علي" في قوائم
    الأدوات يبتر أشهر أسماء الرواة. هذا الاختبار يحرس ذلك.
    """
    v = classify_entity(label)
    assert v.accepted, f"{label} رُفض خطأً"
    assert v.cleaned_label == cleaned


# --- إحالات الأقسام ليست كيانات ------------------------------------------

@pytest.mark.parametrize("label", [
    "من الباب", "في الحديث", "من أبواب أحكام",
    "أبواب نواقض الوضوء", "الباب",
])
def test_section_references_rejected(label):
    assert not classify_entity(label).accepted


def test_book_marker_still_accepted():
    """"كتاب" اسم عام لكنه مؤشر عنوان، فلا يسقط مع الإحالات."""
    v = classify_entity("كتاب الطهارة")
    assert v.accepted and v.kind is EntityKind.BOOK


# --- حراسة عامة -----------------------------------------------------------

@pytest.mark.parametrize("label", [
    "زرارة بن أعين", "عن أحمد بن محم د", "عن سعد بن عبد الله", "عن أبي عبد الله",
])
def test_real_narrators_survive(label):
    assert classify_entity(label).accepted


def test_stripping_never_returns_empty_accepted():
    """التنظيف لا يجوز أن يقبل تسمية فارغة."""
    for label in ["عن", "عن عن", "بن", "من في عن"]:
        v = classify_entity(label)
        assert not v.accepted or v.cleaned_label.strip()


def test_reason_always_present():
    for label in ["محم د بن يعقوب عن", "من الباب", ""]:
        assert classify_entity(label).reason
