"""اختبارات مقسّم الرواية — على القالب الذي حدّده المستخدم."""

from __future__ import annotations

import pytest

from packages.layout.hadith_splitter import (
    HadithSplitter,
    extract_narrators,
    identify_imam,
)

# المثال الذي أعطاه المستخدم، حرفياً
EXAMPLE = (
    "[ 29214 ] 1 ـ محمد بن يعقوب ، عن محمد بن يحيى ، عن أحمد بن محمد ، "
    "عن ابن محبوب ، عن أبي أيوب الخرّاز ، عن محمد بن مسلم ، قال : سألت "
    "أبا جعفر ( عليه السلام ) عن رجل دبر مملوكا له ، ثمّ احتاج إلى ثمنه ، "
    "فقال : هو مملوكه ان شاء باعه ، وان شاء أعتقه ، وان شاء أمسكه حتّى "
    "يموت ، فاذا مات السيد فهو حر من ثلثه ."
)


@pytest.fixture
def splitter():
    return HadithSplitter()


# --- القالب المحدَّد -------------------------------------------------------

def test_number_extracted(splitter):
    assert "29214" in splitter.split(EXAMPLE).number


def test_isnad_ends_after_the_imam_honorific(splitter):
    """
    السند ينتهي بعد "( عليه السلام )" لا عند أول "قال" — لأن
    "قال : سألت أبا جعفر" من كلام الراوي لا من المتن.
    """
    p = splitter.split(EXAMPLE)
    assert p.isnad.endswith(")") or "السلام" in p.isnad[-24:]
    assert "محمد بن مسلم" in p.isnad
    assert "سألت أبا جعفر" in p.isnad


def test_matn_starts_after_the_honorific(splitter):
    p = splitter.split(EXAMPLE)
    assert p.matn.startswith("عن رجل دبر")
    assert "فهو حر من ثلثه" in p.matn


# --- المبدأ الصارم: لا يضيع حرف -------------------------------------------

def test_reassembly_is_byte_exact(splitter):
    """
    إعادة تركيب الأجزاء يجب أن تطابق الأصل حرفاً بحرف.
    هذا ما يضمن ألا يفقد التقسيم حركةً ولا همزةً ولا نقطة.
    """
    p = splitter.split(EXAMPLE)
    rebuilt = (
        EXAMPLE[p.number_span[0] : p.number_span[1]]
        + EXAMPLE[p.isnad_span[0] : p.isnad_span[1]]
        + EXAMPLE[p.matn_span[0] : p.matn_span[1]]
    )
    assert rebuilt == EXAMPLE


@pytest.mark.parametrize("mark,where", [
    ("الخرّاز", "isnad"),
    ("ثمّ", "matn"),
    ("حتّى", "matn"),
    ("أحمد", "isnad"),
    ("أبي", "isnad"),
    ("أعتقه", "matn"),
])
def test_diacritics_and_hamzas_preserved(splitter, mark, where):
    """الشدّات والهمزات تبقى في مواضعها بعد التقسيم."""
    p = splitter.split(EXAMPLE)
    assert mark in getattr(p, where)


# --- سلسلة الرواة ----------------------------------------------------------

def test_narrator_chain_in_order(splitter):
    p = splitter.split(EXAMPLE)
    chain = extract_narrators(p.isnad)
    assert chain[0] == "محمد بن يعقوب"
    assert "محمد بن مسلم" in chain
    assert chain.index("محمد بن يحيى") < chain.index("أحمد بن محمد")


def test_imam_is_not_a_link_in_the_chain(splitter):
    """المعصوم منتهى السند لا حلقة فيه؛ خلطهما يفسد رسم الإسناد."""
    p = splitter.split(EXAMPLE)
    chain = extract_narrators(p.isnad)
    assert not any("جعفر ( عليه" in n for n in chain)
    assert identify_imam(p.isnad) == "أبا جعفر"


def test_transmission_particle_stripped_from_names(splitter):
    p = splitter.split(EXAMPLE)
    for name in extract_narrators(p.isnad):
        assert not name.startswith("عن ")


# --- حالات أخرى من متنك ----------------------------------------------------

def test_arabic_indic_number_form(splitter):
    p = splitter.split(
        "] ٧٦٨ ١ [ محمّد بن يعقوب ، عن عدّة من أصحابنا ، عن أحمد بن محمّد ، "
        "عن أبي عبد الله ( عليه السلام ) قال : الوضوء شطر الإيمان ."
    )
    assert "٧٦٨" in p.number
    assert "الوضوء شطر" in p.matn


def test_sanad_without_matn(splitter):
    p = splitter.split("محمّد بن الحسن بإسناده ، عن الحسين بن سعيد ، عن صفوان بن يحيى ،")
    assert p.isnad and not p.matn


def test_prophetic_matn_without_chain(splitter):
    p = splitter.split("قال رسول الله ( صلى الله عليه وآله ) : الماء يطهر ولا يطهر .")
    assert "الماء يطهر" in p.matn


# --- التحفّظ ---------------------------------------------------------------

def test_low_confidence_leaves_text_whole():
    """التقسيم الخاطئ أضر من غيابه: قد ينسب كلام الراوي إلى المعصوم."""
    strict = HadithSplitter(min_confidence=0.95)
    p = strict.split("قال رسول الله ( صلى الله عليه وآله ) : الماء يطهر .")
    assert not p.isnad


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_input(splitter, value):
    p = splitter.split(value)
    assert not p.isnad and not p.matn and p.confidence == 0.0


def test_every_split_has_a_reason(splitter):
    for text in [EXAMPLE, "نص عادي بلا سند", ""]:
        assert splitter.split(text).reasons
