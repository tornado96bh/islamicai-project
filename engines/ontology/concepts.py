"""
Ontology Engine — التصنيف المفاهيمي.

القسم 8 من المواصفة. الفرق الذي يصنعه:

    البحث عن "الوضوء"   يجد ما فيه لفظ الوضوء
    الأنطولوجيا تعرف أن الوضوء طهارةٌ، وأن الغسل والتيمم أخواته،
    وأن الماء الجاري والكرّ من أدواته

فيصير ممكناً: "كل روايات الطهارة عدا الجبيرة" — وهو سؤال علاقات
لا سؤال ألفاظ.

التوسيع بيانات لا كود: `datasets/ontology/concepts.json`.

schema_version: 1.0.0
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ONTOLOGY_VERSION = "1.0.0"
DEFAULT_PATH = Path("datasets/ontology/concepts.json")


@dataclass(slots=True)
class Concept:
    concept_id: str
    label: str
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    note: str = ""

    def all_terms(self) -> list[str]:
        return [self.label, *self.synonyms]


@dataclass(slots=True)
class ConceptMatch:
    concept: Concept
    matched_term: str
    depth: int = 0
    via: str = "direct"

    def as_dict(self) -> dict:
        return {"concept_id": self.concept.concept_id, "label": self.concept.label,
                "matched_term": self.matched_term, "depth": self.depth, "via": self.via}


def _norm(text: str) -> str:
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


class Ontology:
    """شجرة المفاهيم مع التوسيع والاستبعاد."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self.concepts: dict[str, Concept] = {}
        self._term_index: dict[str, list[str]] = {}
        self.version = ONTOLOGY_VERSION
        self.loaded = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        for row in data.get("concepts", []):
            c = Concept(
                concept_id=str(row.get("id", "")),
                label=str(row.get("label", "")),
                parent=row.get("parent"),
                children=list(row.get("children", [])),
                synonyms=list(row.get("synonyms", [])),
                related=list(row.get("related", [])),
                excludes=list(row.get("excludes", [])),
                note=str(row.get("note", "")),
            )
            if c.concept_id and c.label:
                self.concepts[c.concept_id] = c

        # اشتقاق الأبناء من الآباء: أدقّ من كتابتها مرتين في الملف
        for c in self.concepts.values():
            if c.parent and c.parent in self.concepts:
                parent = self.concepts[c.parent]
                if c.concept_id not in parent.children:
                    parent.children.append(c.concept_id)

        for c in self.concepts.values():
            for term in c.all_terms():
                self._term_index.setdefault(_norm(term), []).append(c.concept_id)

        self.loaded = bool(self.concepts)

    def __len__(self) -> int:
        return len(self.concepts)

    # -----------------------------------------------------------------
    def match(self, text: str) -> list[ConceptMatch]:
        """يجد المفاهيم المذكورة في نص."""
        norm = _norm(text)
        out: list[ConceptMatch] = []
        seen: set[str] = set()
        for term, ids in self._term_index.items():
            if term and term in norm:
                for cid in ids:
                    if cid not in seen:
                        seen.add(cid)
                        out.append(ConceptMatch(self.concepts[cid], term))
        return sorted(out, key=lambda m: -len(m.matched_term))

    def descendants(self, concept_id: str, *, max_depth: int = 5) -> list[str]:
        out: list[str] = []
        queue = deque([(concept_id, 0)])
        seen = {concept_id}
        while queue:
            cid, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for child in self.concepts.get(cid, Concept("", "")).children:
                if child not in seen:
                    seen.add(child)
                    out.append(child)
                    queue.append((child, depth + 1))
        return out

    def ancestors(self, concept_id: str) -> list[str]:
        out: list[str] = []
        current = self.concepts.get(concept_id)
        while current and current.parent:
            out.append(current.parent)
            current = self.concepts.get(current.parent)
        return out

    def expand_query(self, text: str, *, include_children: bool = True,
                     include_synonyms: bool = True) -> dict:
        """
        يوسّع الاستعلام بالمفاهيم لا بالألفاظ.

        "الطهارة" تجلب الوضوء والغسل والتيمم، لأنها فروعها — لا لأن
        ألفاظها متشابهة.
        """
        matches = self.match(text)
        terms: list[str] = []
        excluded: list[str] = []
        used: list[dict] = []

        for m in matches:
            c = m.concept
            used.append(m.as_dict())
            if include_synonyms:
                terms.extend(c.all_terms())
            if include_children:
                for cid in self.descendants(c.concept_id):
                    terms.extend(self.concepts[cid].all_terms())
            for ex in c.excludes:
                if ex in self.concepts:
                    excluded.extend(self.concepts[ex].all_terms())

        seen: set[str] = set()
        unique = [t for t in terms if t and not (t in seen or seen.add(t))]
        return {
            "original": text,
            "concepts": used,
            "expanded_terms": unique[:40],
            "excluded_terms": sorted(set(excluded)),
        }

    def path_to_root(self, concept_id: str) -> list[str]:
        chain = [concept_id] + self.ancestors(concept_id)
        return [self.concepts[c].label for c in chain if c in self.concepts]


__all__ = ["DEFAULT_PATH", "ONTOLOGY_VERSION", "Concept", "ConceptMatch", "Ontology"]
