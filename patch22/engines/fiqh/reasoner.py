"""
Fiqh Engine — ربط المسألة بالأدلة، لا الإفتاء.

حدّ هذا المحرك معلَن
--------------------
**لا يُفتي.** يجمع الأدلة المتصلة بمسألة، ويرتّبها بحسب قوة
دلالتها الظاهرة، ويعرض التعارض إن وُجد — ثم يقف.

الإفتاء اجتهاد يقوم به المجتهد بشروطه، والآلة لا تملكها. وهذا
موافق للمواصفة: "لا حكم تلقائياً" و"إحالة للمراجعة عند نقص الأدلة".

ما يقدّمه فعلاً
---------------
    تحليل المسألة إلى موضوع + حكم مستفسَر عنه
    جمع الأدلة من المفهوم وفروعه
    تصنيف دلالة كل دليل: صريح / ظاهر / مفهوم / غير دال
    عرض المتعارضات وأوجه الجمع
    بيان ما ينقص للحسم

schema_version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

FIQH_VERSION = "1.0.0"


class Ruling(str, Enum):
    OBLIGATORY = "واجب"
    RECOMMENDED = "مستحب"
    PERMISSIBLE = "مباح"
    DISLIKED = "مكروه"
    FORBIDDEN = "حرام"
    VALID = "صحيح"
    INVALID = "باطل"
    UNDETERMINED = "غير محدد"


class Strength(str, Enum):
    EXPLICIT = "صريح"        # نصّ في الحكم
    APPARENT = "ظاهر"        # يدل بظاهره
    IMPLIED = "مفهوم"        # يدل بمفهومه
    WEAK = "ضعيف الدلالة"
    IRRELEVANT = "غير دال"


# ألفاظ الأحكام كما ترد في النصوص
_RULING_MARKERS: dict[Ruling, tuple[str, ...]] = {
    Ruling.OBLIGATORY: ("يجب", "واجب", "فريضة", "لا بد", "عليه أن"),
    Ruling.RECOMMENDED: ("يستحب", "مستحب", "ينبغي", "أفضل", "سنة"),
    Ruling.PERMISSIBLE: ("يجوز", "لا بأس", "مباح", "لا حرج", "واسع"),
    Ruling.DISLIKED: ("يكره", "مكروه", "لا أحب"),
    Ruling.FORBIDDEN: ("لا يجوز", "حرام", "يحرم", "لا يحل", "نهى"),
    Ruling.VALID: ("يجزئ", "صحيح", "تم", "أجزأه"),
    Ruling.INVALID: ("يعيد", "باطل", "لا يجزئ", "أعاد"),
}

_QUESTION_RE = re.compile(r"^\s*(ما حكم|حكم|هل يجوز|هل يجب|هل يصح|هل يبطل)\s*")


@dataclass(slots=True)
class EvidenceReading:
    evidence_id: str
    text: str
    ruling: Ruling
    strength: Strength
    markers: list[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> dict:
        return {"evidence_id": self.evidence_id, "text": self.text[:180],
                "ruling": self.ruling.value, "strength": self.strength.value,
                "markers": self.markers, "reason": self.reason}


@dataclass(slots=True)
class FiqhAnalysis:
    question: str
    topic: str = ""
    readings: list[EvidenceReading] = field(default_factory=list)
    distribution: dict = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    disclaimer: str = (
        "هذا عرض للأدلة ودلالتها الظاهرة، وليس فتوى. "
        "الاستنباط والترجيح عمل المجتهد بشروطه."
    )

    def as_dict(self) -> dict:
        return {
            "question": self.question, "topic": self.topic,
            "readings": [r.as_dict() for r in self.readings],
            "distribution": self.distribution,
            "conflicts": self.conflicts,
            "missing": self.missing,
            "disclaimer": self.disclaimer,
        }


class FiqhReasoner:
    """يحلّل المسألة ويعرض أدلتها — بلا إفتاء."""

    def __init__(self, ontology=None, contradiction_engine=None):
        self.ontology = ontology
        self.contradiction = contradiction_engine
        self.version = FIQH_VERSION

    # -----------------------------------------------------------------
    def read_evidence(self, evidence_id: str, text: str,
                      topic_terms: list[str] | None = None) -> EvidenceReading:
        """يقرأ دلالة دليل واحد."""
        body = re.sub(r"\s+", " ", text or "")
        if not body:
            return EvidenceReading(evidence_id, "", Ruling.UNDETERMINED,
                                   Strength.IRRELEVANT, reason="فارغ")

        found: list[tuple[Ruling, str]] = []
        for ruling, markers in _RULING_MARKERS.items():
            for m in markers:
                if m in body:
                    found.append((ruling, m))

        if not found:
            return EvidenceReading(
                evidence_id, body, Ruling.UNDETERMINED, Strength.IRRELEVANT,
                reason="لا لفظ حكمي ظاهر",
            )

        # "لا يجوز" تحوي "يجوز" — الأطول أولى
        found.sort(key=lambda p: -len(p[1]))
        ruling, marker = found[0]
        markers = [m for _, m in found]

        # الصراحة: أن يقترن اللفظ الحكمي بموضوع المسألة
        on_topic = True
        if topic_terms:
            on_topic = any(t in body for t in topic_terms)

        if not on_topic:
            strength = Strength.WEAK
            reason = "اللفظ الحكمي في غير موضوع المسألة"
        elif marker in ("يجب", "لا يجوز", "حرام", "واجب", "يحرم"):
            strength = Strength.EXPLICIT
            reason = f"نصّ صريح بلفظ «{marker}»"
        elif ":" in body or "قال" in body:
            strength = Strength.APPARENT
            reason = f"ظاهر في الحكم بلفظ «{marker}»"
        else:
            strength = Strength.IMPLIED
            reason = f"يدل بمفهومه عبر «{marker}»"

        return EvidenceReading(evidence_id, body, ruling, strength, markers, reason)

    def analyse(self, question: str, evidence: list[dict]) -> FiqhAnalysis:
        """
        evidence: [{"id": ..., "text": ...}, ...]
        """
        analysis = FiqhAnalysis(question=question)

        # موضوع المسألة
        stripped = _QUESTION_RE.sub("", question or "").strip()
        topic_terms: list[str] = []
        if self.ontology is not None:
            matches = self.ontology.match(stripped or question)
            if matches:
                concept = matches[0].concept
                analysis.topic = concept.label
                expanded = self.ontology.expand_query(concept.label)
                topic_terms = expanded["expanded_terms"]
        if not analysis.topic:
            analysis.topic = stripped or "غير محدد"
            topic_terms = [w for w in stripped.split() if len(w) > 3]

        # قراءة الأدلة
        for row in evidence:
            reading = self.read_evidence(
                str(row.get("id", "")), str(row.get("text") or ""), topic_terms
            )
            analysis.readings.append(reading)

        # توزيع الأحكام على الأدلة الدالّة
        relevant = [
            r for r in analysis.readings
            if r.strength in (Strength.EXPLICIT, Strength.APPARENT, Strength.IMPLIED)
        ]
        dist: dict[str, int] = {}
        for r in relevant:
            dist[r.ruling.value] = dist.get(r.ruling.value, 0) + 1
        analysis.distribution = dist

        # التعارض
        if self.contradiction is not None and len(relevant) >= 2:
            conflicts = self.contradiction.detect(
                [{"id": r.evidence_id, "text": r.text} for r in relevant]
            )
            analysis.conflicts = [c.as_dict() for c in conflicts]

        # ما ينقص للحسم — يُقال ولا يُتجاوز
        if not relevant:
            analysis.missing.append("لا دليل دالّ على الحكم في النتائج")
        if len(dist) > 1:
            analysis.missing.append(
                f"الأدلة موزّعة على {len(dist)} أحكام — يلزم ترجيح المجتهد"
            )
        if not any(r.strength is Strength.EXPLICIT for r in relevant):
            analysis.missing.append("لا نصّ صريح — الدلالة ظاهرة أو مفهومة فقط")
        if len(relevant) < 2:
            analysis.missing.append("دليل واحد لا يكفي للحسم")

        return analysis


__all__ = ["FIQH_VERSION", "EvidenceReading", "FiqhAnalysis", "FiqhReasoner",
           "Ruling", "Strength"]
