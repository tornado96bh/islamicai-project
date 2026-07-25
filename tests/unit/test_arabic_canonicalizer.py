"""اختبارات المطبّع العربي — خصوصاً سلامة خريطة الإزاحة."""

from __future__ import annotations

import pytest

from packages.utils.arabic_canonicalizer import (
    canonicalize,
    search_form_text,
    tokenize_text,
)


# ---------------------------------------------------------------------------
# 1) توحيد الحروف — هذه كلها كانت تفشل في النسخة القديمة
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "a,b",
    [
        ("إسماعيل", "اسماعيل"),
        ("أحمد", "احمد"),
        ("آمنة", "امنه"),
        ("عيسى", "عيسي"),
        ("صلاة", "صلاه"),
        ("مسؤول", "مسوول"),
        ("مسئول", "مسيول"),
        ("ٱلرحمن", "الرحمن"),
        ("مُحَمَّد", "محمد"),
        ("الرَّحْمَٰن", "الرحمن"),
        ("كــتــاب", "كتاب"),
        ("الكتاب\u200f", "الكتاب"),
        ("١٤٢٣", "1423"),
        ("کتاب", "كتاب"),
    ],
)
def test_letter_folding(a, b):
    assert search_form_text(a) == search_form_text(b)


def test_distinct_words_stay_distinct():
    """الطيّ يجب ألا يدمج كلمات مختلفة فعلاً."""
    assert search_form_text("علي") != search_form_text("عمر")
    assert search_form_text("حسن") != search_form_text("حسين")


# ---------------------------------------------------------------------------
# 2) خريطة الإزاحة — جوهر الملف
# ---------------------------------------------------------------------------

def test_offsets_length_matches_canonical():
    res = canonicalize("قَالَ رَسُولُ اللَّهِ صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ")
    assert len(res.offsets) == len(res.canonical)


def test_offsets_are_monotonic():
    res = canonicalize("بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ")
    assert res.offsets == sorted(res.offsets)


def test_offsets_point_inside_raw():
    res = canonicalize("حَدَّثَنَا أَبُو بَكْرٍ")
    assert all(0 <= o < len(res.raw) for o in res.offsets)


def test_raw_excerpt_recovers_diacritics():
    """
    الاختبار الحاسم: نبحث في الصيغة المطبّعة، ونسترجع النص الأصلي
    بتشكيله من نفس الموضع. هذا ما يحفظ صحة الاستشهاد.
    """
    raw = "قَالَ رَسُولُ اللَّهِ صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ"
    res = canonicalize(raw)

    needle = search_form_text("الاعمال")
    idx = res.canonical.find(needle)
    assert idx != -1, "الكلمة يجب أن توجد في الصيغة المطبّعة"

    excerpt = res.raw_excerpt(idx, idx + len(needle))
    # المقطع المسترجَع يجب أن يحمل التشكيل الأصلي
    assert "َ" in excerpt or "ْ" in excerpt
    # وأن يعود إلى نفس الكلمة بعد تطبيعه
    assert search_form_text(excerpt) == needle


def test_raw_excerpt_on_every_word():
    """دورة كاملة: كل كلمة مطبّعة تُرجع مقطعاً أصلياً يطابقها بعد التطبيع."""
    raw = "إِنَّ الْحَمْدَ لِلَّهِ نَحْمَدُهُ وَنَسْتَعِينُهُ وَنَسْتَغْفِرُهُ"
    res = canonicalize(raw)

    pos = 0
    for word in res.canonical.split(" "):
        if not word:
            pos += 1
            continue
        idx = res.canonical.index(word, pos)
        excerpt = res.raw_excerpt(idx, idx + len(word))
        assert search_form_text(excerpt) == word, f"فشل على: {word!r} -> {excerpt!r}"
        pos = idx + len(word)


def test_offsets_survive_ligature_expansion():
    """صور العرض تتوسع إلى عدة محارف، وكلها تُنسب إلى المحرف الأصلي."""
    raw = "ﻻ إله إلا الله"
    res = canonicalize(raw)
    assert len(res.offsets) == len(res.canonical)
    assert res.offsets == sorted(res.offsets)


# ---------------------------------------------------------------------------
# 3) الحالات الحدّية
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "   ", "\u200f\u200e", "ـــ"])
def test_empty_like_inputs(value):
    res = canonicalize(value)
    assert res.canonical == ""
    assert res.offsets == []
    assert res.to_raw_span(0, 5) == (0, 0)


def test_no_leading_or_trailing_space():
    assert search_form_text("   الكتاب   ") == "الكتاب"


def test_internal_spaces_collapsed():
    assert search_form_text("باب\n\n\tالطهارة") == "باب الطهاره"


def test_ocr_allah_fix():
    assert search_form_text("قال االله تعالى") == search_form_text("قال الله تعالى")


def test_mixed_arabic_latin():
    res = canonicalize("كتاب Sahih البخاري")
    assert "Sahih" in res.canonical
    assert len(res.offsets) == len(res.canonical)


def test_tokenize_drops_empties():
    assert tokenize_text("  باب   الطهارة  ") == ["باب", "الطهاره"]


def test_idempotent():
    """تطبيع المُطبَّع لا يغيّره — شرط لصحة إعادة الفهرسة."""
    for s in ["إسماعيل بن إبراهيم", "الرَّحْمَٰن", "قال ﷺ", "١٤٢٣ هـ"]:
        once = search_form_text(s)
        assert search_form_text(once) == once
