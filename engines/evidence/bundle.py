"""
Evidence Engine — بناء حزمة الأدلة.

موقعه في المواصفة
-----------------
القسم 6.2: "بناء Evidence Bundle موثق" ثم "التحقق من اكتمال الأدلة
والثقة" ثم "صياغة الإجابة النهائية أو الإحالة للمراجعة".

هذا هو التحوّل من **محرك بحث** إلى **منصة توثيق**: النتيجة لم تعد
قائمة روابط، بل حزمةَ أدلة كل قطعة فيها موصولة بموضعها الدقيق.

المبدأ الحاكم (القسم 2)
-----------------------
"لا تخمين عند نقص الأدلة؛ إمّا إجابة موثقة أو إحالة للمراجعة أو
تصريح بعدم كفاية الأدلة."

فالحزمة تحمل درجة اكتمالها، والمحقق بعدها يقرر: تُقدَّم أم تُحال.

schema_version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

EVIDENCE_VERSION = "1.0.0"


class EvidenceKind(str, Enum):
    MATN = "matn"
    ISNAD = "isnad"
    HEADING = "heading"
    FOOTNOTE = "footnote"
    TAKHRIJ = "takhrij"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Provenance:
    """
    مسار المصدر الكامل — القسم 2: "كل قرار قابل للتفسير والتدقيق".

    كل حقل هنا ضروري لإعادة إنتاج النتيجة بعد سنوات: من الكتاب إلى
    العنصر، ومن إصدار المسار إلى إصدار الفهرس.
    """

    book_id: str = ""
    book_title: str = ""
    volume_number: int | None = None
    edition_number: int | None = None
    page_number: int | None = None
    element_id: str = ""
    element_order: int | None = None
    pipeline_version: str = ""
    index_version: str = ""
    ocr_version: str = ""
    normalizer_version: str = ""

    def citation(self) -> str:
        """صيغة استشهاد مقروءة."""
        parts = [self.book_title or "مصدر غير مسمّى"]
        if self.volume_number:
            parts.append(f"ج{self.volume_number}")
        if self.page_number:
            parts.append(f"ص{self.page_number}")
        return " ".join(parts)

    def is_complete(self) -> bool:
        """هل يمكن الاستشهاد به علمياً؟"""
        return bool(self.book_id and self.element_id and self.page_number)


@dataclass(slots=True)
class EvidenceItem:
    """قطعة دليل واحدة، مقتطعة من مصدرها بموضعها."""

    text_raw: str
    text_display: str
    kind: EvidenceKind
    provenance: Provenance
    score: float = 0.0
    ocr_quality: float = 0.0
    hadith_number: str | None = None
    isnad_text: str | None = None
    matn_text: str | None = None
    narrators: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def is_citable(self) -> bool:
        """
        هل يصلح للاستشهاد؟

        النص الرديء المسح لا يصلح مرجعاً علمياً مهما علا ترتيبه —
        وهذا ما يميّز منصة التوثيق عن محرك البحث.
        """
        return self.provenance.is_complete() and self.ocr_quality >= 0.35

    def as_dict(self) -> dict:
        return {
            "text_display": self.text_display,
            "kind": self.kind.value,
            "citation": self.provenance.citation(),
            "score": round(self.score, 5),
            "ocr_quality": round(self.ocr_quality, 4),
            "is_citable": self.is_citable,
            "hadith_number": self.hadith_number,
            "isnad_text": self.isnad_text,
            "matn_text": self.matn_text,
            "narrators": self.narrators,
            "provenance": {
                "book_id": self.provenance.book_id,
                "page_number": self.provenance.page_number,
                "element_id": self.provenance.element_id,
                "pipeline_version": self.provenance.pipeline_version,
            },
        }


@dataclass(slots=True)
class EvidenceBundle:
    """حزمة الأدلة لسؤال واحد."""

    query: str
    intent: str = "general"
    intent_confidence: float = 0.0
    items: list[EvidenceItem] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)
    built_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = EVIDENCE_VERSION

    @property
    def citable(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.is_citable]

    @property
    def coverage(self) -> float:
        """نسبة الأدلة الصالحة للاستشهاد."""
        return round(len(self.citable) / len(self.items), 4) if self.items else 0.0

    @property
    def distinct_sources(self) -> int:
        """عدد المواضع المستقلة — دليلان من صفحة واحدة ليسا مستقلين."""
        return len({(i.provenance.book_id, i.provenance.page_number) for i in self.citable})

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "intent": self.intent,
            "intent_confidence": round(self.intent_confidence, 4),
            "items": [i.as_dict() for i in self.items],
            "citable_count": len(self.citable),
            "coverage": self.coverage,
            "distinct_sources": self.distinct_sources,
            "rejected": [{"element_id": e, "reason": r} for e, r in self.rejected],
            "built_at": self.built_at,
            "schema_version": self.schema_version,
        }


class EvidenceBuilder:
    """
    يبني الحزمة من نتائج البحث الخام.

    يرفض ما لا يصلح دليلاً **ويسجّل سبب الرفض** — فالحذف الصامت
    يخالف قاعدة "كل قرار قابل للتفسير".
    """

    def __init__(self, *, max_items: int = 10, min_ocr_quality: float = 0.2):
        self.max_items = int(max_items)
        self.min_ocr_quality = float(min_ocr_quality)
        self.version = EVIDENCE_VERSION

    def build(self, payload: dict) -> EvidenceBundle:
        intent = payload.get("intent") or {}
        bundle = EvidenceBundle(
            query=payload.get("query", ""),
            intent=str(intent.get("label", "general")),
            intent_confidence=float(intent.get("confidence", 0.0) or 0.0),
        )

        for row in payload.get("results", []):
            explain = row.get("score_explain") or {}
            quality = float(explain.get("sig_ocr_quality", 0.0) or 0.0)
            element_id = str(row.get("element_id") or "")

            if quality < self.min_ocr_quality:
                bundle.rejected.append(
                    (element_id, f"جودة المسح {quality:.2f} دون العتبة")
                )
                continue

            prov = Provenance(
                book_id=str(row.get("book_id") or ""),
                book_title=str(row.get("book_title") or ""),
                volume_number=row.get("volume_number"),
                edition_number=row.get("edition_number"),
                page_number=row.get("page_number"),
                element_id=element_id,
                element_order=row.get("element_order"),
                pipeline_version=str(row.get("ranking_version") or ""),
                index_version=str(row.get("reranker_version") or ""),
            )

            try:
                kind = EvidenceKind(str(row.get("best_element_type") or "unknown"))
            except ValueError:
                kind = EvidenceKind.UNKNOWN

            bundle.items.append(
                EvidenceItem(
                    text_raw=str(row.get("text") or ""),
                    text_display=str(row.get("text_display") or row.get("text") or ""),
                    kind=kind,
                    provenance=prov,
                    score=float(row.get("score", 0.0) or 0.0),
                    ocr_quality=quality,
                    hadith_number=row.get("hadith_number"),
                    isnad_text=row.get("isnad_text"),
                    matn_text=row.get("matn_text"),
                    reasons=list(row.get("reasons") or []),
                )
            )
            if len(bundle.items) >= self.max_items:
                break

        return bundle


__all__ = [
    "EVIDENCE_VERSION", "EvidenceBuilder", "EvidenceBundle", "EvidenceItem",
    "EvidenceKind", "Provenance",
]
