"""
Narrator Engine — قاموس الرواة والربط.

موقعه في المواصفة
-----------------
القسم 8: "Narrator Engine: التمييز بين الأسماء المتشابهة."
وهو المعوّق الأول: بدونه لا Isnad Graph ولا Knowledge Graph ولا
Contradiction Detection.

المنهج
------
لا ينتظر قاعدة رواة ضخمة. يبدأ بقاموس بذرة (gazetteer) من كبار
رواة الكتب الأربعة، ويربط بالمطابقة الدقيقة أولاً ثم بالكنية
والنسبة ثم بالتقريب.

الاسم غير المعروف **لا يُخترع له معرّف**؛ يُرجَّع بحالة `unresolved`
مع درجة، فيراه المحقق ويضيفه. القسم 2: "لا تخمين عند نقص الأدلة".

التوسيع: أضف مدخلات إلى datasets/gazetteer/narrators.json — لا
تعديل في الكود.

schema_version: 1.0.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

GAZETTEER_VERSION = "1.1.0"

DEFAULT_PATH = Path("datasets/gazetteer/narrators.json")


class Resolution(str, Enum):
    EXACT = "exact"            # مطابقة اسم أو لقب مسجَّل
    ALIAS = "alias"            # مطابقة كنية أو نسبة
    FUZZY = "fuzzy"            # تقريب — يحتاج تأكيد
    AMBIGUOUS = "ambiguous"    # أكثر من مرشّح
    UNRESOLVED = "unresolved"  # غير معروف — يُضاف يدوياً


@dataclass(slots=True)
class Narrator:
    """
    الراوي ككيان كامل لا كنص.

    الحقول الفارغة مقصودة: تُملأ تدريجياً بمراجعة بشرية، ولا
    يُخترع لها قيم.
    """

    narrator_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    kunya: str = ""
    nisba: str = ""
    generation: int | None = None      # الطبقة
    death_year: int | None = None      # سنة الوفاة هجرياً
    reliability: str = ""              # التوثيق — لا يُحكم آلياً
    teachers: list[str] = field(default_factory=list)
    students: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    note: str = ""

    def all_forms(self) -> list[str]:
        forms = [self.canonical_name, *self.aliases]
        if self.kunya:
            forms.append(self.kunya)
        return [f for f in forms if f]


@dataclass(slots=True)
class ResolutionResult:
    query: str
    resolution: Resolution
    narrator: Narrator | None = None
    score: float = 0.0
    candidates: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.resolution in (Resolution.EXACT, Resolution.ALIAS)

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "resolution": self.resolution.value,
            "narrator_id": self.narrator.narrator_id if self.narrator else None,
            "canonical_name": self.narrator.canonical_name if self.narrator else None,
            "score": round(self.score, 4),
            "candidates": self.candidates,
            "reason": self.reason,
        }


# سوابق تلتصق بالاسم في السند فتمنع مطابقته:
#   "وعن محمد بن يحيى"  و  "عن أحمد بن محمد"  و  "، عن الحسين"
# إزالتها رفعت نسبة الربط من نحو الثلث إلى الأغلب.
_LEADING_PARTICLES = (
    "وعن ", "فعن ", "ثم عن ", "عن ", "وعنه عن ", "عنه عن ", "و ", "ف ",
    "حدثنا ", "حدّثنا ", "أخبرنا ", "اخبرنا ", "وباسناده عن ",
    "وبإسناده عن ", "باسناده عن ", "بإسناده عن ",
)

# لواحق تلتصق بالذيل
_TRAILING_PARTICLES = (" عن", " قال", " رحمه الله", " رضي الله عنه", " ،")


def strip_particles(name: str) -> str:
    """
    ينزع أدوات العطف والتحمّل من طرفي الاسم.

    يُعاد التطبيق حتى الاستقرار: "وعن عن فلان" واردة في OCR.
    """
    out = (name or "").strip(" .،:؛()[]«»")
    changed = True
    while changed and out:
        changed = False
        for p in _LEADING_PARTICLES:
            if out.startswith(p):
                out = out[len(p):].strip()
                changed = True
                break
        for suffix in _TRAILING_PARTICLES:
            if out.endswith(suffix):
                out = out[: -len(suffix)].strip(" .،:؛")
                changed = True
                break
    return out


def _norm(text: str) -> str:
    """تطبيع للمطابقة فقط — لا يمس المخزَّن."""
    out = []
    for ch in text or "":
        o = ord(ch)
        if 0x064B <= o <= 0x065F or o in (0x0670, 0x0640):
            continue
        if o in (0x0622, 0x0623, 0x0625, 0x0671):
            out.append("\u0627")
        elif o == 0x0649:
            out.append("\u064a")
        elif o == 0x0629:
            out.append("\u0647")
        else:
            out.append(ch)
    return " ".join("".join(out).split())


class NarratorGazetteer:
    """
    قاموس الرواة مع الربط.

    يُحمَّل من ملف JSON، فالتوسيع بيانات لا كود.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self.narrators: dict[str, Narrator] = {}
        self._index: dict[str, list[str]] = {}
        self.version = GAZETTEER_VERSION
        self.loaded = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return

        for row in payload.get("narrators", []):
            n = Narrator(
                narrator_id=str(row.get("id", "")),
                canonical_name=str(row.get("canonical_name", "")),
                aliases=list(row.get("aliases", [])),
                kunya=str(row.get("kunya", "")),
                nisba=str(row.get("nisba", "")),
                generation=row.get("generation"),
                death_year=row.get("death_year"),
                reliability=str(row.get("reliability", "")),
                teachers=list(row.get("teachers", [])),
                students=list(row.get("students", [])),
                source_refs=list(row.get("source_refs", [])),
                note=str(row.get("note", "")),
            )
            if not n.narrator_id or not n.canonical_name:
                continue
            self.narrators[n.narrator_id] = n
            # صيغ الاسم قد تتطابق بعد التطبيع ("علي بن إبراهيم" و
            # "علي بن ابراهيم")؛ فبلا إزالة التكرار يُحسب الراوي
            # الواحد مرشحَين ويصير الحكم ambiguous خطأً.
            for form in {_norm(f) for f in n.all_forms()}:
                bucket = self._index.setdefault(form, [])
                if n.narrator_id not in bucket:
                    bucket.append(n.narrator_id)

        self.loaded = bool(self.narrators)

    def __len__(self) -> int:
        return len(self.narrators)

    # -----------------------------------------------------------------
    def resolve(self, name: str) -> ResolutionResult:
        """يربط اسماً بكيان راوٍ، أو يصرّح بأنه غير معروف."""
        raw = (name or "").strip()
        if not raw:
            return ResolutionResult(raw, Resolution.UNRESOLVED, reason="فارغ")

        # التنظيف قبل المطابقة: "وعن محمد بن يحيى" لا تطابق شيئاً،
        # و"محمد بن يحيى" تطابق فوراً.
        cleaned = strip_particles(raw)
        if not cleaned:
            return ResolutionResult(
                raw, Resolution.UNRESOLVED, reason="أدوات فقط بلا اسم"
            )

        key = _norm(cleaned)
        hits = self._index.get(key, [])

        if len(hits) == 1:
            n = self.narrators[hits[0]]
            exact = _norm(n.canonical_name) == key
            return ResolutionResult(
                raw, Resolution.EXACT if exact else Resolution.ALIAS,
                n, 1.0 if exact else 0.9,
                reason="مطابقة الاسم المعتمد" if exact else "مطابقة كنية أو لقب",
            )

        if len(hits) > 1:
            return ResolutionResult(
                raw, Resolution.AMBIGUOUS, None, 0.5,
                candidates=[self.narrators[h].canonical_name for h in hits],
                reason=f"{len(hits)} مرشحين — يحتاج تمييزاً",
            )

        # تقريب على مستوى الكلمات لا المحارف.
        #
        # "احمد بن محمد بن عيسى الاشعري" و "أحمد بن محمد بن عيسى"
        # تشتركان في أربع كلمات؛ المقارنة المحرفية تعطيهما 0.7 فقط
        # لأن اللاحقة تطيل أحدهما. المقارنة بالكلمات أدق للأعلام.
        key_words = set(key.split())
        best_id, best_score = None, 0.0
        for form, ids in self._index.items():
            form_words = set(form.split())
            if len(form_words) < 2 or len(key_words) < 2:
                continue
            shared = key_words & form_words
            if len(shared) < 2:
                continue
            score = len(shared) / max(len(key_words), len(form_words))
            if score > best_score:
                best_score, best_id = score, ids[0]

        if best_id and best_score >= 0.6:
            return ResolutionResult(
                raw, Resolution.FUZZY, self.narrators[best_id], round(best_score, 4),
                reason="تقريب — يحتاج تأكيد المحقق",
            )

        return ResolutionResult(
            raw, Resolution.UNRESOLVED, None, 0.0,
            reason="غير مسجَّل في القاموس — يُضاف بمراجعة بشرية",
        )

    def resolve_chain(self, names: list[str]) -> list[ResolutionResult]:
        return [self.resolve(n) for n in names]

    def coverage(self, names: list[str]) -> float:
        if not names:
            return 0.0
        got = sum(1 for r in self.resolve_chain(names) if r.resolved)
        return round(got / len(names), 4)


__all__ = [
    "DEFAULT_PATH",
    "strip_particles", "GAZETTEER_VERSION", "Narrator", "NarratorGazetteer",
    "Resolution", "ResolutionResult",
]
