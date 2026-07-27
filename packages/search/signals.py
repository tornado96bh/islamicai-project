"""
إشارات الترتيب التمييزية.

المشكلة التي تحلها
------------------
في مخرجاتك، الإشارات الأربع متطابقة في **كل** النتائج العشرين:

    signals: 0.022   exact_raw: 0.02   layout: 0.012   rerank: 0.014

فالترتيب يحدده rrf_base وحده، ومداه ضيق (0.011 إلى 0.021). النتيجة
أن الفرق بين الأولى والعشرين 0.011 فقط — لا يميّز الممتاز من المتوسط.

السبب أن كل الإشارات ثنائية: تتحقق أو لا. واستعلام مثل «الله» يحقق
شروطها كلها في كل نتيجة، فتصير إزاحة ثابتة لا إشارة.

الحل
----
إشارات **متدرّجة** تُحسب من خصائص النتيجة نفسها:

  1. جودة OCR      كثافة التمديد، الشظايا، الترقيم داخل الكلمات
  2. تغطية الاستعلام  نسبة كلمات الاستعلام الموجودة، لا وجودها فقط
  3. اكتمال النص    هل يبدأ أو ينتهي مبتوراً؟
  4. كثافة الاستعلام  عدد مرات الورود نسبةً إلى طول النص

كل واحدة ترجّع عدداً في [0,1]، ثم تُوزن في نطاق أساس RRF نفسه
(~0.02) — درس الدفعة الثالثة: أي إشارة تتجاوز حجم الأساس تبتلعه.

عطب النسخة 1.0.0 (مُصلَح هنا)
----------------------------
جُعلت جودة OCR **مكافأة**، فصار القِصَر يُكافأ: السطر القصير النظيف
ينال 1.00 بينما الفقرة الطويلة الممدّدة تنال 0.04. والنتيجة:

  * ارتباط الإشارات بـ rrf_base = **−0.93**، أي أنها تُلغيه بدل
    أن تكمّله. المدى الكلي انكمش من 0.0129 إلى 0.0051.
  * صعدت إلى العشرين الأولى عباراتٌ نمطية ("إن شاء الله تعالى")
    وسطرُ فهرسٍ بأرقام: "اسم الله . . . ....... 01 768 678".
  * وارتفع must_contain_rate إلى 0.875 لأنها كلها تحوي "الله" —
    فالمقياس كافأ التدهور.

الإصلاح
-------
  1. جودة OCR صارت **عقوبة فقط**: النظيف ينال صفراً لا مكافأة،
     والمعطوب ينال سالباً. فلا يُكافأ القِصَر.
  2. سابقة الطول: الفقرة ذات المحتوى تُرجَّح على السطر القصير.
  3. الإفادة: النص المكوَّن من عبارات نمطية شائعة يُخفَّض.
  4. كشف سطور الفهارس: تتابع النقاط والأرقام الذيلية.

schema_version: 1.1.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SIGNALS_VERSION = "1.3.0"

_TATWEEL = "\u0640"
# يقبل الحركات: بدونها "محمّد" لا تُعدّ رمزاً عربياً أصلاً، فلا
# تُحسب ولا تُستثنى، وينحرف عدّ الشظايا.
_ARABIC_RE = re.compile(r"^[\u0621-\u064a\u064b-\u0652\u0670]+$")

# الطول يُقاس بالحروف لا بالمحارف: "محمّ" أربعة حروف لا خمسة
_LETTERS_ONLY_RE = re.compile(r"[\u0621-\u064a]")


def _letter_count(token: str) -> int:
    return len(_LETTERS_ONLY_RE.findall(token))


# كلمات عربية صحيحة من حرفين. عدّها شظايا هو ما جعل النص السليم
# ينال درجةً متدنية: "عن أبيه ، عن سعد" فيها أربع "شظايا" مزعومة.
_SHORT_REAL_WORDS = frozenset({
    "عن", "من", "في", "ما", "لا", "ان", "إن", "أن", "به", "له", "هو",
    "هي", "قد", "بن", "كل", "لم", "لن", "او", "أو", "يا", "ثم", "مع",
    "هذ", "ذا", "بل", "عن", "اي", "أي", "اذ", "إذ", "كم", "لك", "بك",
})


def _is_fragment(token: str) -> bool:
    """
    شظية = رمز عربي قصير **ليس** كلمة قائمة بذاتها.

    التمييز ضروري: بدونه يُعاقَب كل سند صحيح، لأن "عن" تتكرر فيه.
    """
    if not _ARABIC_RE.match(token):
        return False
    stripped = "".join(_LETTERS_ONLY_RE.findall(token))
    return len(stripped) <= 2 and stripped not in _SHORT_REAL_WORDS
_LONE_PUNCT = {"،", ",", ".", ":", ";", "؛", "-", "(", ")", "[", "]"}

# نفس قاعدة المصحّح: الفاصل بعد الحركة عطب طباعي لا فاصل كلمات
_DIACRITIC_SPLIT_RE = re.compile(
    r"([\u0621-\u064a][\u064b-\u0652\u0670])\s+([\u0621-\u064a]{1,2})(?=\s|$|[^\u0621-\u064a])"
)

# نص يبدأ أو ينتهي بهذه لا يكون جملة تامة
_OPENERS_INCOMPLETE = {"،", "و", "ف", ":", "(", ")"}


@dataclass(slots=True)
class SignalScores:
    """كل إشارة على حدة، لتظهر في score_explain مفصَّلة."""

    ocr_quality: float = 1.0
    coverage: float = 0.0
    completeness: float = 1.0
    density: float = 0.0
    length_prior: float = 0.0
    informativeness: float = 1.0

    def weighted(self, weights: dict[str, float]) -> float:
        """
        جودة OCR تدخل **كعقوبة** لا كمكافأة.

        بقيّتها مكافآت. الفرق جوهري: لو دخلت الجودةُ مكافأةً لكافأنا
        السطرَ القصير النظيف على الفقرة المفيدة، وهو ما حدث فعلاً في
        النسخة السابقة.
        """
        penalty = (1.0 - self.ocr_quality) * weights.get("ocr_penalty", 0.0)
        bonus = (
            self.coverage * weights.get("coverage", 0.0)
            + self.completeness * weights.get("completeness", 0.0)
            + self.density * weights.get("density", 0.0)
            + self.length_prior * weights.get("length_prior", 0.0)
            + self.informativeness * weights.get("informativeness", 0.0)
        )
        return bonus - penalty

    def as_dict(self) -> dict[str, float]:
        return {
            "sig_ocr_quality": round(self.ocr_quality, 4),
            "sig_coverage": round(self.coverage, 4),
            "sig_completeness": round(self.completeness, 4),
            "sig_density": round(self.density, 4),
            "sig_length_prior": round(self.length_prior, 4),
            "sig_informativeness": round(self.informativeness, 4),
        }


# أوزان في حجم أساس RRF. مجموعها الأقصى 0.030، أي في مستوى الأساس
# لا فوقه. القياس على المجموعة الذهبية هو ما يعدّلها، لا الحدس.
DEFAULT_WEIGHTS = {
    "ocr_penalty": 0.010,      # عقوبة، تُطرح
    "coverage": 0.008,
    "completeness": 0.004,
    "density": 0.002,          # خُفّض: كان يكافئ القصير المكرر
    "length_prior": 0.008,     # جديد: يرجّح الفقرة ذات المحتوى
    "informativeness": 0.006,  # جديد: يخفّض العبارات النمطية
}

# عبارات نمطية تتكرر بكثرة ولا تحمل معلومة تخص الاستعلام.
# مشتقة من متنك: أشيع ما صعد خطأً إلى صدارة النتائج.
BOILERPLATE_PATTERNS = (
    "ان شا الله", "إن شاء الله", "الحمد لله", "الحمد الله",
    "صلي الله عليه واله", "صلى الله عليه وآله",
    "عليه السلام", "عليهم السلام", "عز وجل", "عزّ وجلّ", "تبارك وتعالي",
)


def ocr_quality(raw_text: str) -> float:
    """
    يقدّر سلامة النص الأصلي.

    النص الممدّد أو المفكّك يُسترجَع بقوة (التمديد يولّد ثلاثيات
    متكررة ترفع تشابه trigram زوراً)، لكنه أسوأ للقارئ. هذه الإشارة
    تخفضه دون إقصائه.
    """
    if not raw_text:
        return 0.0

    length = len(raw_text)
    tatweel_ratio = raw_text.count(_TATWEEL) / length

    # الشظايا تُحسب على النص **بعد** إزالة التمديد.
    #
    # وإلا فـ"بـــــن" تُعدّ رمزاً طويلاً و"محمّـــــد" كلمتين، فينال
    # النص المقروء درجةً أسوأ من "االله" المعطوب فعلاً. هذا ما رأيتَه:
    # sig_ocr_quality = 0 لنصوص سليمة.
    clean = raw_text.replace(_TATWEEL, "")

    # ثم يُصلَح الشقّ بعد الحركة قبل عدّ الشظايا.
    #
    # "محمّـــــ د" بعد إزالة التمديد تصير "محمّ د" — شظيةً في العدّ،
    # مع أن المصحّح يلحمها إلى "محمّد" بلا خسارة. فقياس الجودة على
    # نص لم يمر بالتصحيح يعاقب ما سيُصلَح فعلاً.
    clean = _DIACRITIC_SPLIT_RE.sub(r"\1\2", clean)
    tokens = clean.split()
    if not tokens:
        return 0.0

    # شظايا: رموز عربية من حرف أو حرفين
    fragments = sum(1 for t in tokens if _is_fragment(t))
    fragment_ratio = fragments / len(tokens)

    # ترقيم يقع بين شظيتين عربيتين: علامة تفكّك داخل الكلمة
    inner_punct = 0
    for i in range(1, len(tokens) - 1):
        if tokens[i] in _LONE_PUNCT:
            a, b = tokens[i - 1], tokens[i + 1]
            if (_is_fragment(a) or _is_fragment(b)) and _ARABIC_RE.match(
                a
            ) and _ARABIC_RE.match(b):
                inner_punct += 1
    inner_ratio = inner_punct / max(len(tokens), 1)

    # التمديد الطباعي ليس فشلاً بصرياً.
    #
    # "محمّـــــد بـــــن يحـــــيى" مقروء تماماً؛ التمديد تنسيقُ صفحة
    # يزيله المصحّح بلا خسارة. أما "االله" فخطأ قراءة يغيّر الحروف.
    # إعطاؤهما الدرجة نفسها (صفر) جعل نصوصاً سليمة تُرفض من حزمة
    # الأدلة، فانخفضت التغطية وصار المحقق يمتنع بلا سبب حقيقي.
    #
    # فوزن التمديد خُفّض إلى الثلث، ووزن التفكّك الحقيقي رُفع.
    # "االله" و "ا الله": ألف زائدة قبل لفظ الجلالة — خطأ قراءة يغيّر
    # الحروف نفسها، وهو أخطر من التمديد لأنه لا يُزال بحذف محرف.
    misread = len(re.findall(r"\u0627\u0627\u0644\u0644\u0647|\u0627\s\u0627\u0644\u0644\u0647", clean))
    misread_ratio = min(1.0, misread / max(len(tokens), 1) * 4)

    # إشارتان إضافيتان تمنعان تشبّع المقياس عند 1.00.
    #
    # كان نصّان مختلفا الجودة ينالان 1.00 معاً، فيصير المقياس
    # ثنائياً عملياً: سليم أو معطوب، بلا درجات بينهما. والترتيب
    # والتحقق يُبنيان عليه، فيحتاجان تدرّجاً حقيقياً.

    # (أ) كثافة الترقيم المنفصل: "، عن" و ") :" علامة نصّ مقطّع
    lone_punct = sum(1 for t in tokens if t in _LONE_PUNCT)
    punct_ratio = lone_punct / max(len(tokens), 1)

    # (ب) اتساق طول الكلمات: التذبذب الشديد أثر تقطيع لا لغة
    lengths = [_letter_count(t) for t in tokens if _ARABIC_RE.match(t)]
    if len(lengths) >= 4:
        mean = sum(lengths) / len(lengths)
        variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        irregularity = min(1.0, variance / 12.0)
    else:
        irregularity = 0.0

    damage = min(
        1.0,
        tatweel_ratio * 0.7
        + fragment_ratio * 1.4
        + inner_ratio * 2.2
        + misread_ratio * 1.2
        + punct_ratio * 0.45
        + irregularity * 0.25,
    )
    return round(max(0.0, 1.0 - damage), 4)


def query_coverage(query_tokens: list[str], text_tokens: list[str]) -> float:
    """نسبة كلمات الاستعلام الموجودة فعلاً — لا مجرد وجود واحدة."""
    if not query_tokens:
        return 0.0
    present = set(text_tokens)
    found = sum(1 for t in query_tokens if t in present)
    return round(found / len(query_tokens), 4)


def completeness(text: str) -> float:
    """
    هل النتيجة جملة تامة أم مقطع مبتور؟

    مخرجاتك مليئة بأسطر تبدأ أو تنتهي في منتصف الجملة، لأن التقطيع
    على مستوى السطر لا الجملة. النتيجة التامة أنفع للقارئ.
    """
    s = (text or "").strip()
    if not s:
        return 0.0

    score = 1.0
    tokens = s.split()
    if not tokens:
        return 0.0

    if tokens[0] in _OPENERS_INCOMPLETE:
        score -= 0.35
    # ينتهي بلا علامة ختام
    if s[-1] not in {".", "؟", "!", "۔"}:
        score -= 0.25
    # قصير جداً
    if len(tokens) < 5:
        score -= 0.25
    # شظية مبتورة في الطرف (حرف أو حرفان)
    if len(tokens[-1].replace(_TATWEEL, "")) <= 2 and _ARABIC_RE.match(
        tokens[-1].replace(_TATWEEL, "")
    ):
        score -= 0.15

    return round(max(0.0, score), 4)


def term_density(query_tokens: list[str], text_tokens: list[str]) -> float:
    """
    تكرار كلمات الاستعلام نسبةً إلى الطول.

    يفرّق بين نصّ يذكر الكلمة عرضاً ونصّ يدور حولها. مُشبَّع عند 0.25
    حتى لا يفوز النص القصير المكرر.
    """
    if not query_tokens or not text_tokens:
        return 0.0
    q = set(query_tokens)
    hits = sum(1 for t in text_tokens if t in q)
    return round(min(1.0, (hits / len(text_tokens)) / 0.25), 4)


def length_prior(n_words: int) -> float:
    """
    يرجّح الفقرة ذات المحتوى على السطر القصير.

    السطر من أربع كلمات نادراً ما يكون أفضل جواب، مهما كان نظيفاً.
    والفقرة الطويلة جداً تُخفَّض قليلاً لأنها تُفقد التركيز.
    """
    if n_words <= 3:
        return 0.0
    if n_words < 8:
        return round((n_words - 3) / 5 * 0.6, 4)
    if n_words <= 30:
        return 1.0
    return round(max(0.6, 1.0 - (n_words - 30) / 60), 4)


def informativeness(normalized_text: str) -> float:
    """
    يخفّض النص الذي معظمه عبارات نمطية.

    "ذلك ان شا الله تعالي ." و "الحمد الله رب العالمين ." نظيفتان
    وقصيرتان، فارتفعتا خطأً في النسخة السابقة. لكنهما لا تحملان
    معلومة تخص أي استعلام تقريباً.
    """
    text = (normalized_text or "").strip()
    if not text:
        return 0.0
    tokens = text.split()
    if not tokens:
        return 0.0

    covered = 0
    for pattern in BOILERPLATE_PATTERNS:
        if pattern in text:
            covered += len(pattern.split())
    ratio = min(1.0, covered / len(tokens))
    return round(max(0.0, 1.0 - ratio), 4)


_DOT_RUN_RE = re.compile(r"[.\u2024\u2026]{4,}|(?:\.\s){4,}")
_DIGIT_TAIL_RE = re.compile(r"[\d\u0660-\u0669\s.\u0640-]{12,}$")


def looks_like_index_line(text: str) -> bool:
    """
    سطر فهرس: تتابع نقاط ثم أرقام صفحات.

        "اسم الله . . . ....... 01 768 678 033"

    نال جودة 0.98 في النسخة السابقة ودخل العشرين الأولى.
    """
    s = text or ""
    return bool(_DOT_RUN_RE.search(s)) or bool(_DIGIT_TAIL_RE.search(s))


def compute_signals(
    *,
    raw_text: str,
    normalized_text: str,
    query_tokens: list[str],
) -> SignalScores:
    text_tokens = [t for t in (normalized_text or "").split() if t]

    quality = ocr_quality(raw_text or "")
    if looks_like_index_line(normalized_text or ""):
        quality = min(quality, 0.15)

    return SignalScores(
        ocr_quality=quality,
        coverage=query_coverage(query_tokens, text_tokens),
        completeness=completeness(normalized_text or ""),
        density=term_density(query_tokens, text_tokens),
        length_prior=length_prior(len(text_tokens)),
        informativeness=informativeness(normalized_text or ""),
    )


__all__ = [
    "BOILERPLATE_PATTERNS",
    "DEFAULT_WEIGHTS",
    "SIGNALS_VERSION",
    "SignalScores",
    "compute_signals",
    "completeness",
    "informativeness",
    "length_prior",
    "looks_like_index_line",
    "ocr_quality",
    "query_coverage",
    "term_density",
]
