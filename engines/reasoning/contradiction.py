"""
Contradiction Engine — كشف التعارض وأوجه الجمع.

ما يطلبه المستخدم: ليس "وُجد تعارض" بل:

    وُجد تعارض → سببه → نوعه → هل هو ظاهري → عام أم خاص →
    مطلق أم مقيد → وجوه الجمع → ثم يترك الترجيح للمحقق

المبدأ الحاكم (القسم 2 من المواصفة)
-----------------------------------
"لا حكم تلقائياً". فالمحرك **يعرض** أوجه الجمع الممكنة ولا يختار
بينها. اختيار وجه على وجه اجتهادٌ فقهي، وهو عمل العالِم لا الآلة.

schema_version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

CONTRADICTION_VERSION = "1.0.0"


class ConflictType(str, Enum):
    NEGATION = "negation"            # يجوز / لا يجوز
    OBLIGATION = "obligation"        # واجب / مستحب
    PURITY = "purity"                # طاهر / نجس
    QUANTITY = "quantity"            # مقادير مختلفة
    ATTRIBUTION = "attribution"      # نُسب لمعصومين مختلفين
    NONE = "none"


class ReconciliationKind(str, Enum):
    GENERAL_SPECIFIC = "general_specific"    # عام وخاص
    ABSOLUTE_RESTRICTED = "absolute_restricted"  # مطلق ومقيد
    DIFFERENT_CASE = "different_case"        # موضوعان مختلفان
    ABROGATION = "abrogation"                # نسخ
    TAQIYYA = "taqiyya"                      # تقية
    GRADING = "grading"                      # اختلاف في الصحة
    UNRESOLVED = "unresolved"


# أزواج متضادة، مع نوع التعارض
_OPPOSITES: tuple[tuple[str, str, ConflictType], ...] = (
    ("يجوز", "لا يجوز", ConflictType.NEGATION),
    ("يجب", "لا يجب", ConflictType.OBLIGATION),
    ("واجب", "مستحب", ConflictType.OBLIGATION),
    ("لا بأس", "لا يجوز", ConflictType.NEGATION),
    ("طاهر", "نجس", ConflictType.PURITY),
    ("يطهر", "لا يطهر", ConflictType.PURITY),
    ("حلال", "حرام", ConflictType.NEGATION),
    ("يعيد", "لا يعيد", ConflictType.OBLIGATION),
    ("عليه", "ليس عليه", ConflictType.OBLIGATION),
)

# قرائن التخصيص والتقييد
_SPECIFIER_MARKERS = ("إلا", "الا", "إذا", "اذا", "إن كان", "ان كان",
                      "في حال", "عند", "ما لم", "بشرط")
_QUANTITY_RE = re.compile(r"[\u0660-\u06690-9]+|كرّ|كر|رطل|مدّ|مد|صاع")
_IMAM_RE = re.compile(
    r"(أبا جعفر|ابا جعفر|أبي جعفر|ابي جعفر|أبا عبد الله|ابا عبد الله|"
    r"أبي عبد الله|ابي عبد الله|أبا الحسن|ابا الحسن|الرضا|الصادق|الباقر)"
)


@dataclass(slots=True)
class Reconciliation:
    kind: ReconciliationKind
    explanation: str
    confidence: float = 0.0

    def as_dict(self) -> dict:
        return {"kind": self.kind.value, "explanation": self.explanation,
                "confidence": round(self.confidence, 4)}


@dataclass(slots=True)
class Conflict:
    left_id: str
    right_id: str
    conflict_type: ConflictType
    trigger: tuple[str, str]
    left_text: str = ""
    right_text: str = ""
    shared_topic: str = ""
    reconciliations: list[Reconciliation] = field(default_factory=list)
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "left_id": self.left_id, "right_id": self.right_id,
            "type": self.conflict_type.value,
            "trigger": {"left": self.trigger[0], "right": self.trigger[1]},
            "left_text": self.left_text[:200], "right_text": self.right_text[:200],
            "shared_topic": self.shared_topic,
            "reconciliations": [r.as_dict() for r in self.reconciliations],
            "note": self.note,
        }


class ContradictionEngine:
    """
    يكشف التعارض ويقترح أوجه الجمع.

    ontology اختيارية: بها يعرف المحرك أن النصين في موضوع واحد،
    وبدونها يعتمد على تقاطع الألفاظ وحده.
    """

    def __init__(self, ontology=None, *, min_shared_words: int = 3):
        self.ontology = ontology
        self.min_shared_words = int(min_shared_words)
        self.version = CONTRADICTION_VERSION

    # -----------------------------------------------------------------
    def detect(self, items: list[dict]) -> list[Conflict]:
        """
        items: [{"id": ..., "text": ...}, ...]

        يقارن كل زوج. التكلفة تربيعية، لكن المدخل أعلى النتائج
        (عشرة عادةً) لا الفهرس كله.
        """
        conflicts: list[Conflict] = []
        n = len(items)

        for i in range(n):
            for j in range(i + 1, n):
                a, b = items[i], items[j]
                conflict = self._compare(a, b)
                if conflict is not None:
                    conflicts.append(conflict)

        return conflicts

    def _compare(self, a: dict, b: dict) -> Conflict | None:
        ta = re.sub(r"\s+", " ", str(a.get("text") or ""))
        tb = re.sub(r"\s+", " ", str(b.get("text") or ""))
        if not ta or not tb:
            return None

        # يجب أن يكونا في موضوع واحد، وإلا فلا تعارض بل اختلاف موضوع
        topic = self._shared_topic(ta, tb)
        if not topic:
            return None

        for left, right, kind in _OPPOSITES:
            # الطرفان في نصّين مختلفين، لا في جملة مبيِّنة واحدة
            a_has_left = left in ta and right not in ta
            b_has_right = right in tb
            b_has_left = left in tb and right not in tb
            a_has_right = right in ta

            if a_has_left and b_has_right:
                pair, trigger = (a, b), (left, right)
            elif b_has_left and a_has_right:
                # الترتيب يتبع النصّين لا اللفظين: النصّ الحامل
                # للطرف الأول يبقى أولاً، وإلا اختلّ شرح وجه الجمع
                pair, trigger = (b, a), (left, right)
            else:
                continue

            first, second = pair
            first_text = ta if first is a else tb
            second_text = tb if first is a else ta
            # `_suggest` تفحص القرائن في النصين معاً، والترتيب هنا
            # يحدد أيهما "الأول" في شرح وجه الجمع فحسب.

            conflict = Conflict(
                left_id=str(first.get("id", "")),
                right_id=str(second.get("id", "")),
                conflict_type=kind,
                trigger=trigger,
                left_text=first_text,
                right_text=second_text,
                shared_topic=topic,
            )
            conflict.reconciliations = self._suggest(first_text, second_text, kind)
            conflict.note = "تُعرض أوجه الجمع ولا يُرجَّح بينها — الترجيح للمحقق"
            return conflict

        return None

    def _shared_topic(self, a: str, b: str) -> str:
        """هل النصّان في موضوع واحد؟"""
        if self.ontology is not None:
            ca = {m.concept.concept_id for m in self.ontology.match(a)}
            cb = {m.concept.concept_id for m in self.ontology.match(b)}
            shared = ca & cb
            if shared:
                cid = sorted(shared)[0]
                return self.ontology.concepts[cid].label

        stop = {"في", "من", "عن", "على", "الى", "ما", "لا", "ان", "قال",
                "الله", "عليه", "السلام", "به", "له", "هو", "هي", "ثم"}
        wa = {w for w in a.split() if len(w) > 2 and w not in stop}
        wb = {w for w in b.split() if len(w) > 2 and w not in stop}
        shared_words = wa & wb
        if len(shared_words) >= self.min_shared_words:
            return " ".join(sorted(shared_words)[:3])
        return ""

    def _suggest(self, a: str, b: str, kind: ConflictType) -> list[Reconciliation]:
        """
        يقترح أوجه الجمع المعروفة عند الأصوليين.

        الاقتراح مبني على قرائن نصية ظاهرة، لا على اجتهاد. وكل وجه
        يحمل ثقةً منخفضة عمداً: هو **احتمال يُعرض** لا حكم يُتبنّى.
        """
        out: list[Reconciliation] = []

        a_spec = [m for m in _SPECIFIER_MARKERS if m in a]
        b_spec = [m for m in _SPECIFIER_MARKERS if m in b]

        if a_spec and not b_spec:
            out.append(Reconciliation(
                ReconciliationKind.GENERAL_SPECIFIC,
                f"الأول مقيَّد بـ«{a_spec[0]}» والثاني مطلق — "
                "فقد يكون الأول مخصِّصاً للثاني",
                0.55,
            ))
        elif b_spec and not a_spec:
            out.append(Reconciliation(
                ReconciliationKind.GENERAL_SPECIFIC,
                f"الثاني مقيَّد بـ«{b_spec[0]}» والأول مطلق — "
                "فقد يكون الثاني مخصِّصاً للأول",
                0.55,
            ))

        qa, qb = _QUANTITY_RE.findall(a), _QUANTITY_RE.findall(b)
        if (qa or qb) and set(qa) != set(qb):
            out.append(Reconciliation(
                ReconciliationKind.ABSOLUTE_RESTRICTED,
                "المقادير مختلفة بين النصين — قد يكون أحدهما مقيِّداً للآخر",
                0.45,
            ))

        ia, ib = _IMAM_RE.findall(a), _IMAM_RE.findall(b)
        if ia and ib and set(ia) != set(ib):
            out.append(Reconciliation(
                ReconciliationKind.DIFFERENT_CASE,
                f"نُسب الأول إلى «{ia[0]}» والثاني إلى «{ib[0]}» — "
                "قد يكون اختلاف حال أو سائل",
                0.4,
            ))
            out.append(Reconciliation(
                ReconciliationKind.TAQIYYA,
                "اختلاف المعصوم قد يُحمل على التقية عند بعض الأصوليين — "
                "لا يُصار إليه إلا بقرينة",
                0.2,
            ))

        if kind is ConflictType.PURITY and not out:
            out.append(Reconciliation(
                ReconciliationKind.DIFFERENT_CASE,
                "قد يختلف الحكم باختلاف نوع الماء أو مقداره",
                0.35,
            ))

        if not out:
            out.append(Reconciliation(
                ReconciliationKind.UNRESOLVED,
                "لا قرينة ظاهرة للجمع — يحتاج نظر المحقق في السند والسياق",
                0.0,
            ))

        return out

    def report(self, conflicts: list[Conflict]) -> dict:
        by_type: dict[str, int] = {}
        for c in conflicts:
            by_type[c.conflict_type.value] = by_type.get(c.conflict_type.value, 0) + 1
        resolvable = sum(
            1 for c in conflicts
            if any(r.kind is not ReconciliationKind.UNRESOLVED
                   for r in c.reconciliations)
        )
        return {
            "count": len(conflicts),
            "by_type": by_type,
            "with_suggested_reconciliation": resolvable,
            "conflicts": [c.as_dict() for c in conflicts],
            "principle": "النظام يعرض التعارض وأوجه الجمع، ولا يرجّح",
        }


__all__ = ["CONTRADICTION_VERSION", "Conflict", "ConflictType",
           "ContradictionEngine", "Reconciliation", "ReconciliationKind"]
