"""
اختبارات الدفعة الرابعة عشرة.

كل حالة هنا مأخوذة من مخرجاتك الفعلية — عيوب ظهرت في التشغيل لا في
التخيّل، بعضها أدخلتُه أنا في دفعات سابقة.
"""

from __future__ import annotations

import json

import pytest

from packages.ingestion.ocr_corrector import Lexicon, OcrCorrector
from packages.layout.hadith_splitter import HadithSplitter
from packages.learning.entity_filter import classify_entity


@pytest.fixture
def corrector(tmp_path):
    words = {
        "محمد": 2651, "حماد": 400, "الصفار": 200, "عليه": 16901, "عبد": 10779,
        "الله": 19673, "امن": 900, "موا": 300, "من": 9000, "في": 9000,
        "بن": 12000, "عن": 15000, "د": 16359, "محم": 13427, "حم": 5000,
        "اد": 3000, "ع": 1186, "ا": 8000, "م": 4000,
    }
    p = tmp_path / "dictionary.json"
    p.write_text(json.dumps(
        {"entries": [{"word": w, "frequency": f} for w, f in words.items()]},
        ensure_ascii=False), encoding="utf-8")
    return OcrCorrector(Lexicon(p))


# ===========================================================================
#  1) الدمج الخاطئ — عيب أدخلتُه في دفعة سابقة
# ===========================================================================

@pytest.mark.parametrize("text", [
    "تعمله الله فليكن نقيّ ًا من الدنس .",
    "مّ وأُ هاتنا يا رسول الله",
    "إنّ : الله خلق العقل",
    "عن أبيه ، عن سعد بن عبد الله",
])
def test_no_false_merge(corrector, text):
    """
    "نقيّ ًا من" صارت "نقيّ ًامن" لأن الحماية كانت تُفحص على الجانب
    الأقصر وحده: الشظية "ًا" مفتاحها "ا" فلم تُفحص "من" المحمية.
    """
    out, stats = corrector.correct(text)
    assert stats.words_merged == 0, f"دُمج خطأً: {stats.merged_examples}"


def test_standalone_letters_are_not_fragments(corrector):
    """الحرف الذي يقف كلمةً مستقلة ليس شظية مبتورة."""
    for text in ["و الله أعلم", "ا لكتاب هنا", "م ن الباب"]:
        _, stats = corrector.correct(text)
        assert stats.words_merged == 0, text


@pytest.mark.parametrize("broken,expected", [
    ("عن أحمد بن محمّ ، د عن علي", "محمّد"),
    ("عن حمّ ، اد عن حريز", "حمّاد"),
    ("عن الصفّ ، ار عن", "الصفّار"),
    ("محمّ د بن يعقوب", "محمّد"),
    ("عبد الله ) ع ليه السلام (", "عليه"),
])
def test_correct_merges_still_work(corrector, broken, expected):
    """الإصلاح يجب ألا يعطّل اللحم الصحيح."""
    out, stats = corrector.correct(broken)
    assert expected in out and stats.words_merged >= 1


# ===========================================================================
#  2) الكيانات الملوّثة بالترقيم
# ===========================================================================

@pytest.mark.parametrize("label", [
    "النبي ) صلي الله عليه",
    "الله ) صلي الله عليه",
    "أبي عبد الله ( عليه السلام",
])
def test_punctuation_in_entity_rejected(label):
    """علامات الترقيم وصيغ الصلاة ليست جزءاً من اسم شخص."""
    v = classify_entity(label)
    assert not v.accepted
    assert v.reason


@pytest.mark.parametrize("label,cleaned", [
    ("محمد بن يعقوب", "محمد بن يعقوب"),
    ("علي بن ابراهيم", "علي بن ابراهيم"),
    ("علي بن الحكم عن", "علي بن الحكم"),
    ("سعد بن عبد الله", "سعد بن عبد الله"),
])
def test_real_narrators_survive(label, cleaned):
    v = classify_entity(label)
    assert v.accepted and v.cleaned_label == cleaned


def test_ali_still_guarded():
    """التطبيع يوحّد "على" الجارّة مع "علي" الاسم — حراسة دائمة."""
    assert classify_entity("علي بن ابراهيم").cleaned_label.startswith("علي")


# ===========================================================================
#  3) تقسيم ما ليس رواية
# ===========================================================================

@pytest.fixture
def splitter():
    return HadithSplitter()


@pytest.mark.parametrize("text", [
    "الله عليهم ( قال : قال رسول الله ) صلي الله عليه واله ( : يؤمر برج ال",
    "فمن أحب الله عز وجل أحب ه الله ، ومن أحب ه الله تعالى كان من الآ منين",
    "الله به الجن وإن ه ليصوم اليوم تطوعا يريد به وجه الله",
])
def test_non_report_text_is_not_split(splitter, text):
    """
    كان التقسيم يُطبَّق على كل نص فأنتج matn_text = ": قال" وأمثالها.
    الشرط الآن: سلسلة إسناد ظاهرة أو رقم رواية.
    """
    p = splitter.split(text)
    assert not p.isnad, f"قُسّم خطأً: {p.isnad[:40]}"


def test_real_report_still_splits(splitter):
    p = splitter.split(
        "[ 29214 ] 1 ـ محمد بن يعقوب ، عن محمد بن يحيى ، عن أحمد بن محمد ، "
        "عن محمد بن مسلم ، قال : سألت أبا جعفر ( عليه السلام ) عن رجل دبر "
        "مملوكا له ، ثمّ احتاج إلى ثمنه ."
    )
    assert "29214" in p.number
    assert "محمد بن يعقوب" in p.isnad
    assert p.matn.startswith("عن رجل دبر")
    assert p.confidence >= 0.8


def test_two_word_tail_is_not_a_matn(splitter):
    """": قال" ليست متناً بل بقية جملة."""
    p = splitter.split(
        "محمد بن يعقوب ، عن أحمد بن محمد ، عن أبي عبد الله ( عليه السلام ) : قال"
    )
    assert not p.matn or len(p.matn.split()) >= 3


# ===========================================================================
#  4) الاستيراد الكسول
# ===========================================================================

def test_session_import_does_not_build_an_engine():
    """
    كان استيراد أي شيء من packages.learning يوقظ سلسلة تنتهي ببناء
    محرك PostgreSQL، فينهار جمع الاختبارات بلا مشغّل قاعدة بيانات.
    """
    from packages.database import session

    assert session.get_engine.cache_info().currsize == 0, "بُني محرك عند الاستيراد"
    assert callable(session.SessionLocal)


def test_lazy_attribute_access_is_declared():
    import packages.learning as learning

    assert "LearningTrainer" in dir(learning)
