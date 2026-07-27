from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import json
import math

from .dictionary import search_form_text, tokenize_text
from .entity_filter import classify_entity


def _is_storable_entity(label: str) -> bool:
    """
    هل يستحق هذا المرشّح أن يُخزَّن أصلاً؟

    كان الفلتر يُطبَّق عند العرض فقط، فامتلأ entities.json بشظايا
    مثل "................ ابن بابويه القمي" و "البيت عليهم السلام
    لاحيا التراث". ثم بنت أداةُ المجموعة الذهبية أسئلتَها منه فخرجت
    أسئلة فاسدة.

    الترشيح عند التخزين يمنع التلوّث من مصدره.
    """
    text = (label or "").strip()
    if not text or len(text) > 60:
        return False
    # نقاط الفهارس والأرقام لا تدخل الكيانات
    if "...." in text or ".. ." in text:
        return False
    digits = sum(1 for ch in text if ch.isdigit() or "\u0660" <= ch <= "\u0669")
    if digits > 2:
        return False
    return classify_entity(text).accepted

TRIGGER_KIND = {
    "الإمام": "person",
    "الامام": "person",
    "الشيخ": "person",
    "السيد": "person",
    "السيّد": "person",
    "النبي": "person",
    "الرسول": "person",
    "الكتاب": "book",
    "كتاب": "book",
    "سورة": "quran",
    "آية": "quran",
    "باب": "section",
    "حديث": "hadith",
    "رواية": "hadith",
    "المؤلف": "person",
    "المصنف": "person",
}
GENEALOGY_MARKERS = {"بن", "ابن", "بنت"}
ROLE_MARKERS = {"عليه", "عليها", "عليهم", "عليهما", "رضي", "رحمه", "قدس", "سلام", "صلّى", "صلى"}


@dataclass(slots=True)
class EntityCandidate:
    label: str
    kind: str
    frequency: int = 0
    document_frequency: int = 0
    score: float = 0.0
    examples: list[str] = field(default_factory=list)


class EntityLearner:
    def __init__(self, storage_path: str | Path | None = None):
        default_path = Path(__file__).resolve().parents[2] / "storage" / "learning" / "entities.json"
        self.storage_path = Path(storage_path) if storage_path else default_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.entities: dict[str, EntityCandidate] = {}
        self._loaded = False
        self.load()

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self.storage_path.exists() or self.storage_path.stat().st_size == 0:
            return

        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            return

        for item in payload.get("entities", []):
            try:
                candidate = EntityCandidate(**item)
                self.entities[candidate.label] = candidate
            except Exception:
                continue

    def save(self) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entities": [asdict(entity) for entity in self.entities.values()],
        }
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _join(tokens: Iterable[str]) -> str:
        return " ".join(token for token in tokens if token).strip()

    def learn_label(self, label: str | None, kind: str = "entity", evidence: str | None = None, score_boost: float = 0.0) -> None:
        normalized = self._join(search_form_text(token) for token in tokenize_text(label))
        if not normalized:
            return

        # الترشيح عند التخزين لا عند العرض فقط.
        # بدونه امتلأ entities.json بشظايا مثل
        #   "................ ابن بابويه القمي"
        #   "البيت عليهم السلام لاحيا التراث"
        # ثم بنت أداةُ المجموعة الذهبية أسئلتها منه فخرجت فاسدة.
        if not _is_storable_entity(normalized):
            return

        candidate = self.entities.get(normalized)
        if candidate is None:
            candidate = EntityCandidate(label=normalized, kind=kind)

        candidate.frequency += 1
        candidate.document_frequency += 1
        candidate.score = max(candidate.score, score_boost + math.log1p(candidate.frequency))

        if evidence:
            snippet = evidence[:180].replace("\n", " ").strip()
            if snippet and snippet not in candidate.examples:
                candidate.examples.append(snippet)
                candidate.examples = candidate.examples[:5]

        self.entities[normalized] = candidate

    def learn_text(self, text: str | None, source: str | None = None) -> int:
        return self.learn_tokens(tokenize_text(text), source=source)

    def learn_tokens(self, tokens: Iterable[str], source: str | None = None) -> int:
        items = [search_form_text(token) for token in tokens if search_form_text(token)]
        if not items:
            return 0

        learned = 0
        seen: set[str] = set()
        max_span = 5

        for i, token in enumerate(items):
            kind = TRIGGER_KIND.get(token)

            if kind:
                start = i
                end = min(len(items), i + max_span)
                phrase = self._join(items[start:end])
                if len(phrase.split()) >= 2:
                    self.learn_label(phrase, kind=kind, evidence=source, score_boost=1.5)
                    seen.add(phrase)
                    learned += 1

            if token in GENEALOGY_MARKERS:
                start = max(0, i - 2)
                end = min(len(items), i + 3)
                phrase = self._join(items[start:end])
                if len(phrase.split()) >= 3:
                    self.learn_label(phrase, kind="person", evidence=source, score_boost=2.0)
                    seen.add(phrase)
                    learned += 1

            if token in ROLE_MARKERS and i + 1 < len(items):
                start = max(0, i - 1)
                end = min(len(items), i + 4)
                phrase = self._join(items[start:end])
                if len(phrase.split()) >= 3:
                    self.learn_label(phrase, kind="person", evidence=source, score_boost=1.0)
                    seen.add(phrase)
                    learned += 1

        for i in range(len(items) - 1):
            pair = self._join(items[i : i + 2])
            if pair in seen:
                continue
            if any(marker in pair for marker in ("كتاب", "الإمام", "الشيخ", "السيد", "النبي", "الرسول", "باب", "حديث", "سورة", "آية")):
                self.learn_label(pair, kind="candidate", evidence=source, score_boost=0.75)
                learned += 1

        return learned

    def suggest(self, query: str, limit: int = 10) -> list[dict]:
        q = self._join(search_form_text(token) for token in tokenize_text(query))
        if not q:
            return []

        ranked: list[tuple[float, EntityCandidate]] = []
        for candidate in self.entities.values():
            score = candidate.score
            if q == candidate.label:
                score += 2.5
            elif q in candidate.label:
                score += 1.25
            elif candidate.label in q:
                score += 0.75
            score += math.log1p(candidate.frequency) / 10.0
            score += math.log1p(candidate.document_frequency) / 20.0
            if score >= 0.25:
                ranked.append((score, candidate))

        ranked.sort(key=lambda item: (item[0], item[1].frequency, item[1].label), reverse=True)

        # ---------------------------------------------------------------
        # فلترة بنيوية قبل الإخراج.
        #
        # التكرار وحده لا يميّز الكيان من العبارة الوظيفية: "من الباب"
        # تكررت 6552 مرة لأنها صيغة إحالة في الهوامش، لا لأنها اسم.
        # الفلتر يرفضها ويستبقي "أحمد بن محمد"، وينظّف "عن أحمد بن محمد"
        # إلى "أحمد بن محمد".
        # ---------------------------------------------------------------
        out: list[dict] = []
        for score, item in ranked:
            if len(out) >= limit:
                break

            verdict = classify_entity(item.label)
            if not verdict.accepted:
                continue

            out.append(
                {
                    "label": verdict.cleaned_label or item.label,
                    "original_label": item.label,
                    "kind": verdict.kind.value,
                    "score": round(score, 4),
                    "frequency": item.frequency,
                    "document_frequency": item.document_frequency,
                    "examples": item.examples,
                    "filter_reason": verdict.reason,
                }
            )

        return out

    def __len__(self) -> int:
        return len(self.entities)
