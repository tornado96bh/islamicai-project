"""اختبارات الدفعة الثامنة — الإصلاح التكراري للكلمات المشقوقة."""

from __future__ import annotations

import importlib.util
import re
from collections import Counter
from pathlib import Path

import pytest

# نحمّل الدوال بلا تبعيات قاعدة البيانات
_SRC = (Path(__file__).resolve().parents[2] / "scripts" / "repair_split_words.py").read_text(
    encoding="utf-8"
)
_head = _SRC.split("def build_vocabulary")[0]
for _bad in (
    "from sqlalchemy import func, select",
    "from packages.database.models import PageElement",
    "from packages.database.session import SessionLocal",
):
    _head = _head.replace(_bad, "")
_body = "def repair_line" + _SRC.split("def repair_line")[1].split("def main")[0]
_ns: dict = {}
exec(_head + _body, _ns)
repair_line = _ns["repair_line"]


def vocab_from(lines: list[str]) -> Counter:
    v: Counter = Counter()
    for line in lines:
        for token in line.split():
            if re.match(r"^[\u0621-\u064a]+$", token):
                v[token] += 1
    return v


@pytest.fixture
def vocab():
    """معجم فيه الصيغ الصحيحة بترددات كافية."""
    return vocab_from(
        ["عن حماد عن الحلبي"] * 5
        + ["عن الصفار عن احمد"] * 5
        + ["محمد بن يعقوب عن علي"] * 6
        + ["عن ابراهيم بن هاشم"] * 4
    )


# --- اللحم المتجاور ------------------------------------------------------

def test_adjacent_split_merged(vocab):
    out = repair_line("عن حريز ، عن محم د بن مسلم", vocab, Counter())
    assert "محمد" in out


# --- اللحم عبر علامة ترقيم ----------------------------------------------

@pytest.mark.parametrize("broken,expected", [
    ("عمير ، عن حم ، اد عن الحلبي", "حماد"),
    ("عن الصف ، ار عن احمد", "الصفار"),
    ("عن احمد بن محم ، د عن البرقي", "محمد"),
])
def test_punctuation_split_merged(vocab, broken, expected):
    out = repair_line(broken, vocab, Counter())
    assert expected in out


# --- الحراسات -------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "قال رسول الله ، الماء يطهر ولا يطهر",
    "عن ابيه ، عن سعد بن عبد الله",
    "في الحديث 1 ، من الباب 4",
    "عن ابي عبد الله ) عليه السلام ( ، مثله",
])
def test_valid_text_untouched(vocab, text):
    assert repair_line(text, vocab, Counter()) == text


def test_protected_words_never_merged(vocab):
    for text in ["الحسن ، عن سعيد", "الباب ، من ابواب", "احمد ، بن محمد"]:
        assert repair_line(text, vocab, Counter()) == text


def test_unknown_target_not_merged(vocab):
    """ما لا ينتج كلمة معروفة بتردد كافٍ يُترك."""
    assert repair_line("زقط ، خبل", vocab, Counter()) == "زقط ، خبل"


def test_rare_target_not_merged():
    """الصيغة الصحيحة النادرة (< 3) لا تكفي لتبرير اللحم."""
    v = vocab_from(["عن حماد عن الحلبي"])  # مرة واحدة فقط
    assert repair_line("عن حم ، اد عن", v, Counter()) == "عن حم ، اد عن"


def test_digits_never_merged(vocab):
    assert repair_line("الحديث 1 ، 2 من الباب", vocab, Counter()) == "الحديث 1 ، 2 من الباب"


# --- التقارب --------------------------------------------------------------

def test_repair_is_idempotent(vocab):
    once = repair_line("عن حم ، اد عن الحلبي", vocab, Counter())
    v2 = vocab_from([once] * 5)
    v2.update(vocab)
    assert repair_line(once, v2, Counter()) == once


def test_iteration_converges():
    """كل تمريرة ترفع ترددات الصيغ الصحيحة حتى يتوقف اللحم."""
    lines = ["عن حماد عن الحلبي"] * 4 + ["عن حم ، اد عن الحلبي"] * 3
    merges_per_pass = []
    for _ in range(4):
        v = vocab_from(lines)
        stats: Counter = Counter()
        lines = [repair_line(l, v, stats) for l in lines]
        merges_per_pass.append(sum(stats.values()))
        if merges_per_pass[-1] == 0:
            break
    assert merges_per_pass[0] > 0
    assert merges_per_pass[-1] == 0, "التكرار يجب أن يتقارب"


def test_every_merge_is_recorded(vocab):
    stats: Counter = Counter()
    repair_line("عن حم ، اد عن الحلبي", vocab, stats)
    assert stats, "كل لحم يجب أن يُسجَّل للمراجعة"


@pytest.mark.parametrize("text", ["", "   ", "كلمة", "،"])
def test_edge_inputs(vocab, text):
    assert repair_line(text, vocab, Counter()) == text
