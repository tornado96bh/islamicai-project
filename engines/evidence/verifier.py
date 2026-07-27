"""
Verifier Engine + Final Answer — القسمان 6.2 و 8.

المبدأ الذي ينفّذه
------------------
القسم 2: "لا تخمين عند نقص الأدلة؛ إمّا إجابة موثقة أو إحالة
للمراجعة أو تصريح بعدم كفاية الأدلة."

فهذا المحرك **يرفض** الإجابة حين لا تكفي الأدلة، ولا يخفّف الشروط
ليخرج بشيء. الرفض المعلَّل نتيجة صحيحة، والإجابة الضعيفة ليست كذلك.

معايير التحقق
-------------
    التغطية      هل الأدلة الصالحة كافية عدداً؟
    الاستقلال    هل هي من مواضع مستقلة أم من صفحة واحدة؟
    الجودة       هل النص صالح للاستشهاد؟
    الاتساق      هل بين الأدلة تعارض ظاهر؟
    وضوح النية   هل السؤال مفهوم أصلاً؟

كل معيار يعطي درجة وسبباً، والقرار النهائي مركّب منها ومفسَّر.

schema_version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .bundle import EvidenceBundle

VERIFIER_VERSION = "1.0.0"


class Verdict(str, Enum):
    ANSWERABLE = "answerable"          # أدلة كافية
    PARTIAL = "partial"                # أدلة ناقصة، تُقدَّم بتحفّظ
    NEEDS_REVIEW = "needs_review"      # تُحال لمحقق بشري
    INSUFFICIENT = "insufficient"      # لا تكفي — يُصرَّح بذلك


@dataclass(slots=True)
class Check:
    name: str
    passed: bool
    score: float
    detail: str = ""


@dataclass(slots=True)
class VerificationResult:
    verdict: Verdict
    confidence: float
    checks: list[Check] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    schema_version: str = VERIFIER_VERSION

    @property
    def may_answer(self) -> bool:
        return self.verdict in (Verdict.ANSWERABLE, Verdict.PARTIAL)

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "may_answer": self.may_answer,
            "checks": [
                {"name": c.name, "passed": c.passed,
                 "score": round(c.score, 4), "detail": c.detail}
                for c in self.checks
            ],
            "conflicts": self.conflicts,
            "missing": self.missing,
            "schema_version": self.schema_version,
        }


# أزواج تدل على تعارض ظاهر بين نصين
_CONTRADICTION_PAIRS = (
    ("يجوز", "لا يجوز"), ("يجب", "لا يجب"), ("لا بأس", "لا يجوز"),
    ("طاهر", "نجس"), ("يطهر", "لا يطهر"), ("نعم", "لا"),
)


class Verifier:
    """
    محرك التحقق.

    العتبات معلنة في المُنشئ لا مدفونة في الكود، فيمكن تشديدها
    للأسئلة الحسّاسة وتخفيفها للاستكشاف.
    """

    def __init__(
        self,
        *,
        min_citable: int = 2,
        min_distinct_sources: int = 2,
        min_intent_confidence: float = 0.4,
        answerable_threshold: float = 0.7,
        partial_threshold: float = 0.5,
    ):
        self.min_citable = int(min_citable)
        self.min_distinct_sources = int(min_distinct_sources)
        self.min_intent_confidence = float(min_intent_confidence)
        self.answerable_threshold = float(answerable_threshold)
        self.partial_threshold = float(partial_threshold)
        self.version = VERIFIER_VERSION

    # -----------------------------------------------------------------
    def verify(self, bundle: EvidenceBundle) -> VerificationResult:
        checks: list[Check] = []
        missing: list[str] = []

        # 1) وضوح النية
        clear = bundle.intent_confidence >= self.min_intent_confidence
        checks.append(Check(
            "وضوح النية", clear, bundle.intent_confidence,
            f"ثقة النية {bundle.intent_confidence:.2f}",
        ))
        if not clear:
            missing.append("السؤال غير محدد النية — يُطلب توضيحه")

        # 2) عدد الأدلة الصالحة
        n = len(bundle.citable)
        enough = n >= self.min_citable
        checks.append(Check(
            "عدد الأدلة", enough, min(1.0, n / max(self.min_citable, 1)),
            f"{n} دليلاً صالحاً من {len(bundle.items)}",
        ))
        if not enough:
            missing.append(f"يلزم {self.min_citable} أدلة صالحة على الأقل")

        # 3) استقلال المواضع
        distinct = bundle.distinct_sources
        independent = distinct >= self.min_distinct_sources
        checks.append(Check(
            "استقلال المواضع", independent,
            min(1.0, distinct / max(self.min_distinct_sources, 1)),
            f"{distinct} موضعاً مستقلاً",
        ))
        if not independent:
            missing.append("الأدلة من موضع واحد — لا تعاضد بينها")

        # 4) جودة النص
        quality = (
            sum(i.ocr_quality for i in bundle.citable) / len(bundle.citable)
            if bundle.citable else 0.0
        )
        good = quality >= 0.5
        checks.append(Check(
            "جودة النص", good, quality, f"متوسط جودة المسح {quality:.2f}",
        ))
        if not good:
            missing.append("جودة المسح منخفضة — يُنصح بمراجعة الأصل")

        # 5) الاتساق
        conflicts = self._detect_conflicts(bundle)
        consistent = not conflicts
        checks.append(Check(
            "الاتساق", consistent, 1.0 if consistent else 0.4,
            "لا تعارض ظاهر" if consistent else f"{len(conflicts)} تعارض محتمل",
        ))

        # --- القرار ---------------------------------------------------
        weights = {
            "وضوح النية": 0.25, "عدد الأدلة": 0.25, "استقلال المواضع": 0.2,
            "جودة النص": 0.2, "الاتساق": 0.1,
        }
        confidence = round(
            sum(c.score * weights.get(c.name, 0.0) for c in checks), 4
        )

        if conflicts:
            verdict = Verdict.NEEDS_REVIEW
        elif confidence >= self.answerable_threshold and enough and independent:
            verdict = Verdict.ANSWERABLE
        elif confidence >= self.partial_threshold and n >= 1:
            verdict = Verdict.PARTIAL
        else:
            verdict = Verdict.INSUFFICIENT

        return VerificationResult(verdict, confidence, checks, conflicts, missing)

    @staticmethod
    def _detect_conflicts(bundle: EvidenceBundle) -> list[str]:
        """
        كشف تعارض ظاهر بين نصين.

        لا يحكم بالترجيح — القسم 2: "لا حكم تلقائياً". يعرض التعارض
        ليقرر المحقق البشري.
        """
        found: list[str] = []
        texts = [(i, re.sub(r"\s+", " ", i.matn_text or i.text_display or ""))
                 for i in bundle.citable]
        for a, b in _CONTRADICTION_PAIRS:
            has_a = [t for _, t in texts if a in t and b not in t]
            has_b = [t for _, t in texts if b in t]
            if has_a and has_b:
                found.append(f"تعارض ظاهر بين «{a}» و«{b}»")
        return found


@dataclass(slots=True)
class FinalAnswer:
    """
    الإجابة النهائية — أو الامتناع المعلَّل.

    لا تُنشأ إلا عبر `compose`، فلا يمكن بناء إجابة تتجاوز التحقق.
    """

    query: str
    answered: bool
    verdict: str
    confidence: float
    citations: list[dict] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    refusal_reason: str = ""
    composed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = VERIFIER_VERSION

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "answered": self.answered,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "citations": self.citations,
            "caveats": self.caveats,
            "refusal_reason": self.refusal_reason,
            "composed_at": self.composed_at,
            "schema_version": self.schema_version,
        }


def compose(bundle: EvidenceBundle, result: VerificationResult) -> FinalAnswer:
    """
    يبني الإجابة النهائية من الحزمة وحكم التحقق.

    **لا إجابة بلا استشهاد**: لو خلت الحزمة من دليل صالح فالنتيجة
    امتناع معلَّل مهما كانت الدرجة.
    """
    if not result.may_answer or not bundle.citable:
        return FinalAnswer(
            query=bundle.query,
            answered=False,
            verdict=result.verdict.value,
            confidence=result.confidence,
            refusal_reason="; ".join(result.missing) or "لا أدلة كافية",
            caveats=result.conflicts,
        )

    citations = [
        {
            "text": i.matn_text or i.text_display,
            "citation": i.provenance.citation(),
            "element_id": i.provenance.element_id,
            "hadith_number": i.hadith_number,
            "quality": round(i.ocr_quality, 3),
        }
        for i in bundle.citable
    ]

    caveats = list(result.conflicts)
    if result.verdict is Verdict.PARTIAL:
        caveats.append("الأدلة ناقصة — تُقدَّم بتحفّظ")
    caveats.extend(result.missing)

    return FinalAnswer(
        query=bundle.query,
        answered=True,
        verdict=result.verdict.value,
        confidence=result.confidence,
        citations=citations,
        caveats=caveats,
    )


__all__ = [
    "VERIFIER_VERSION", "Check", "FinalAnswer", "Verdict",
    "VerificationResult", "Verifier", "compose",
]
