"""
OCR Corrector — إصلاح أعطاب المسح الضوئي في النصوص العربية.

يعالج ثلاثة أعطاب موجودة فعلياً في بياناتك:

1. التمديد المفرط (stretch):
       "عــــــــــن وهــــــــــب"  ->  "عن وهب"

2. تفكك الكلمة الواحدة (intra-word split):
       "ع ليه"   ->  "عليه"
       "محم د"   ->  "محمد"
   يُحل بمعجم: نُدمج الجزأين فقط إذا كان الناتج كلمة معروفة
   والجزءان منفردين نادران. هذا يمنع دمج "من الباب" خطأً.

3. رباطات ligature الشائعة:
       "االله"  ->  "الله"

مبدأ حاكم: **لا يُكتب الناتج فوق النص الأصلي أبداً.**
هذه الدالة تُستدعى لإنتاج text_normalized فقط، و text_raw يبقى
كما استُخرج من الملف بكل حركاته وهمزاته ونقاطه.

schema_version: 1.0.0
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

OCR_CORRECTOR_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 1) التمديد
# ---------------------------------------------------------------------------

_TATWEEL = "\u0640"
# ثلاث تطويلات فأكثر = تمديد زخرفي أو عطب مسح، يُحذف
_STRETCH_RE = re.compile(_TATWEEL + "{1,}")

# ---------------------------------------------------------------------------
# 2) الرباطات
# ---------------------------------------------------------------------------

LIGATURE_FIXES = {
    "االله": "الله",
    "االلة": "الله",
    "اللة": "الله",
    "هللا": "الله",
    "اهللا": "الله",
    "رمحن": "رحمن",
}

# ---------------------------------------------------------------------------
# 3) تفكك الكلمة
# ---------------------------------------------------------------------------

# حروف لا تتصل بما بعدها. الكلمة العربية لا تبدأ ببعض الصور،
# لكن الأهم: جزء من حرف أو حرفين غالباً ليس كلمة مستقلة.
_SHORT_FRAGMENT_MAX = 3

# كلمات عربية شرعية قصيرة — لا تُدمج مع ما بعدها أبداً
PROTECTED_SHORT_WORDS = {
    "عن", "في", "من", "الى", "على", "او", "ثم", "قد", "لا", "ما", "بن",
    "ابن", "ابي", "ابو", "اب", "ام", "اذا", "ان", "انه", "به", "له",
    "هو", "هي", "هم", "كل", "بل", "لم", "لن", "يا", "قال", "عند", "بعد",
    "قبل", "غير", "بين", "حتي", "لو", "اي", "كم", "مع", "عليه", "الله",
}


@dataclass(slots=True)
class CorrectionStats:
    """إحصاءات ما غُيّر — للتدقيق والتفسير (الماستر §9)."""

    stretch_removed: int = 0
    ligatures_fixed: int = 0
    words_merged: int = 0
    merged_examples: list[tuple[str, str]] = field(default_factory=list)

    def total(self) -> int:
        return self.stretch_removed + self.ligatures_fixed + self.words_merged


class Lexicon:
    """
    معجم ترددات مبني من نصوصك أنت، لا من قائمة خارجية.

    يُحمَّل من storage/learning/dictionary.json الذي يبنيه LearningTrainer.
    إن لم يوجد، يعمل المصحح بدون دمج الكلمات (يبقى آمناً).
    """

    def __init__(self, path: str | Path | None = None, min_frequency: int = 3):
        self.freq: dict[str, int] = {}
        self.min_frequency = min_frequency
        self.loaded = False
        if path:
            self.load(path)

    def load(self, path: str | Path) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return False
        for item in payload.get("entries", []) or []:
            word = item.get("word")
            if word:
                self.freq[word] = int(item.get("frequency", 0) or 0)
        self.loaded = bool(self.freq)
        return self.loaded

    @staticmethod
    def _key(word: str) -> str:
        """
        مفتاح البحث في المعجم.

        المعجم مبني على الصيغة البحثية (بلا تشكيل، بألف موحّدة)، بينما
        النص هنا ما زال مشكّلاً. بدون هذا التطبيع يفشل البحث عن "محمّد"
        رغم وجود "محمد" في المعجم.
        """
        out = []
        for ch in word:
            o = ord(ch)
            if 0x064B <= o <= 0x065F or o == 0x0670 or o == 0x0640:
                continue
            if o in (0x0622, 0x0623, 0x0625, 0x0671):
                out.append("\u0627")
            elif o == 0x0649:
                out.append("\u064a")
            elif o == 0x0629:
                out.append("\u0647")
            elif o == 0x0624:
                out.append("\u0648")
            elif o == 0x0626:
                out.append("\u064a")
            else:
                out.append(ch)
        return "".join(out)

    def count(self, word: str) -> int:
        return self.freq.get(self._key(word), 0)

    def is_word(self, word: str) -> bool:
        return self.count(word) >= self.min_frequency

    def __len__(self) -> int:
        return len(self.freq)


def remove_stretch(text: str) -> tuple[str, int]:
    """يحذف التطويل. عدّاد لكل موضع أُصلح."""
    if _TATWEEL not in text:
        return text, 0
    count = len(_STRETCH_RE.findall(text))
    return _STRETCH_RE.sub("", text), count


def fix_ligatures(text: str) -> tuple[str, int]:
    """يصلح رباطات OCR على مستوى الكلمة الكاملة فقط."""
    if not text:
        return text, 0
    fixed = 0
    out = []
    for token in text.split(" "):
        repl = LIGATURE_FIXES.get(token)
        if repl is not None:
            out.append(repl)
            fixed += 1
        else:
            out.append(token)
    return " ".join(out), fixed


_ARABIC_ONLY_RE = re.compile(r"^[\u0621-\u064a\u064b-\u065f\u0670\u0671]+$")


def _is_pure_arabic(token: str) -> bool:
    """يمنع لحم الأرقام وعلامات الترقيم (مثل تحويل "1 من" إلى "1من")."""
    return bool(token) and bool(_ARABIC_ONLY_RE.match(token))


def merge_split_words(
    text: str,
    lexicon: Lexicon,
    *,
    stats: CorrectionStats | None = None,
) -> tuple[str, int]:
    """
    يعيد لحم الكلمات المتفككة.

    لا يعتمد على مقارنة الترددات، لأن معجم هذا المتن ملوّث بالعطب نفسه:
    الحرف "د" وحده تردده 16,359 بينما "محمد" الصحيحة 2,651 — فالشظايا
    أشيع من الكلمات السليمة، ومقارنة الترددات تفشل حيث العطب أكثر.

    الشروط المتراكمة قبل أي لحم:
      1. الجزءان حروف عربية خالصة (لا أرقام ولا ترقيم).
      2. الجزء الأقصر بعد التطبيع طوله <= 3.
      3. الجزء الأقصر ليس من الكلمات المحمية ("عن"، "من"، "بن"، "في"...).
      4. الناتج الملحوم كلمة معروفة في المعجم بتردد كافٍ وطوله >= 3.
      5. إن كان الجزء الأقصر بحرفين أو ثلاثة، يُشترط ألا يكون هو نفسه
         كلمة قائمة بذاتها.

    الشرطان 1 و3 هما ما يمنعان "١ من" -> "١من" و "من الباب" -> "منالباب".
    """
    if not lexicon.loaded or not text:
        return text, 0

    tokens = text.split(" ")
    if len(tokens) < 2:
        return text, 0

    out: list[str] = []
    merged = 0
    i = 0

    while i < len(tokens):
        cur = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        did_merge = False

        if cur and nxt and _is_pure_arabic(cur) and _is_pure_arabic(nxt):
            cur_key = lexicon._key(cur)
            nxt_key = lexicon._key(nxt)

            # الجزء الأقصر هو المرشح لأن يكون شظية
            short_key = cur_key if len(cur_key) <= len(nxt_key) else nxt_key

            if (
                len(short_key) <= _SHORT_FRAGMENT_MAX
                and short_key not in PROTECTED_SHORT_WORDS
            ):
                candidate = cur + nxt
                cand_key = lexicon._key(candidate)

                if len(cand_key) >= 3 and lexicon.is_word(candidate):
                    # شظية بحرف واحد تُلحم دائماً؛ الأطول تُلحم فقط إن لم
                    # تكن كلمة قائمة بذاتها
                    ok = len(short_key) == 1 or not lexicon.is_word(short_key)
                    if ok:
                        out.append(candidate)
                        merged += 1
                        if stats is not None and len(stats.merged_examples) < 30:
                            stats.merged_examples.append((f"{cur} {nxt}", candidate))
                        i += 2
                        did_merge = True

        if not did_merge:
            out.append(cur)
            i += 1

    return " ".join(out), merged


class OcrCorrector:
    """
    الواجهة الرئيسية.

    مثال:
        lex = Lexicon("storage/learning/dictionary.json")
        corrector = OcrCorrector(lex)
        clean, stats = corrector.correct("عــــن أبي عبد االله")
    """

    def __init__(self, lexicon: Lexicon | None = None, *, merge_words: bool = True):
        self.lexicon = lexicon or Lexicon()
        self.merge_words = merge_words
        self.version = OCR_CORRECTOR_VERSION

    def correct(self, text: str | None) -> tuple[str, CorrectionStats]:
        stats = CorrectionStats()
        if not text:
            return "", stats

        out = text
        out, stats.stretch_removed = remove_stretch(out)
        out = re.sub(r"\s+", " ", out).strip()
        out, stats.ligatures_fixed = fix_ligatures(out)

        if self.merge_words and self.lexicon.loaded:
            out, stats.words_merged = merge_split_words(out, self.lexicon, stats=stats)

        return out, stats

    def correct_text(self, text: str | None) -> str:
        """نسخة مختصرة ترجّع النص فقط."""
        return self.correct(text)[0]


__all__ = [
    "OCR_CORRECTOR_VERSION",
    "CorrectionStats",
    "Lexicon",
    "OcrCorrector",
    "fix_ligatures",
    "merge_split_words",
    "remove_stretch",
]
