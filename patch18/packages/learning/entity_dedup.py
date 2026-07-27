"""
توحيد الكيانات المكرَّرة.

المشكلة من مخرجاتك
------------------
    "احمد بن محمد"  original: "عن احمد بن محمد عن"   تردد 160
    "احمد بن محمد"  original: "عن احمد بن محمد بن"   تردد 88

نفس الراوي مرتين، لأن التوحيد كان يقع على النص الأصلي لا على
التسمية بعد التنظيف. فيرى الباحث تكراراً بلا معنى، وتتشتت الترددات.

الحل: التجميع على التسمية المنظَّفة، مع جمع الترددات وحفظ كل
الصيغ الأصلية — فلا تضيع معلومة.

schema_version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEDUP_VERSION = "1.0.0"


def _norm_key(label: str) -> str:
    """مفتاح التجميع: تطبيع للمطابقة فقط."""
    out = []
    for ch in label or "":
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


@dataclass(slots=True)
class MergedEntity:
    label: str
    kind: str
    score: float
    frequency: int
    document_frequency: int
    variants: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    filter_reason: str = ""
    merged_count: int = 1

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "kind": self.kind,
            "score": round(self.score, 4),
            "frequency": self.frequency,
            "document_frequency": self.document_frequency,
            "variants": self.variants,
            "examples": self.examples[:5],
            "filter_reason": self.filter_reason,
            "merged_count": self.merged_count,
        }


def deduplicate(suggestions: list[dict], *, limit: int = 8) -> list[dict]:
    """
    يوحّد المرشحين المكرَّرين.

    الترددات تُجمع لأنها لنفس الكيان، والدرجة تُؤخذ من الأعلى لا
    تُجمع — الدرجة قياس صلة لا كمية.
    """
    groups: dict[str, MergedEntity] = {}

    for row in suggestions or []:
        label = str(row.get("label") or "").strip()
        if not label:
            continue
        key = _norm_key(label)
        original = str(row.get("original_label") or label)

        existing = groups.get(key)
        if existing is None:
            groups[key] = MergedEntity(
                label=label,
                kind=str(row.get("kind") or "unknown"),
                score=float(row.get("score", 0.0) or 0.0),
                frequency=int(row.get("frequency", 0) or 0),
                document_frequency=int(row.get("document_frequency", 0) or 0),
                variants=[original],
                examples=list(row.get("examples") or []),
                filter_reason=str(row.get("filter_reason") or ""),
            )
            continue

        existing.frequency += int(row.get("frequency", 0) or 0)
        existing.document_frequency += int(row.get("document_frequency", 0) or 0)
        existing.score = max(existing.score, float(row.get("score", 0.0) or 0.0))
        existing.merged_count += 1
        if original not in existing.variants:
            existing.variants.append(original)
        for ex in row.get("examples") or []:
            if ex not in existing.examples:
                existing.examples.append(ex)
        # التسمية الأطول أدق عادةً
        if len(label) > len(existing.label):
            existing.label = label

    merged = sorted(groups.values(), key=lambda e: -e.score)
    return [m.as_dict() for m in merged[:limit]]


__all__ = ["DEDUP_VERSION", "MergedEntity", "deduplicate"]
