"""
Report Engine — التقرير الشامل.

ما يطلبه المستخدم حرفياً: "يبني تقريراً كاملاً مع التناقضات".

القسم 6.2 يطلب "إجابة موثقة أو إحالة للمراجعة". التقرير هو الصيغة
المقروءة لتلك النتيجة: الإجابة، والأدلة بمواضعها، وسلسلة الرواة،
والتعارضات إن وُجدت، وما يحتاج مراجعة.

مبدأ حاكم
---------
التقرير **لا يرجّح** بين متعارضين. يعرضهما مع سياق كلٍّ منهما ويترك
الحكم للمحقق — القسم 2: "لا حكم تلقائياً".

schema_version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

REPORT_VERSION = "1.0.0"


@dataclass(slots=True)
class ReportSection:
    title: str
    body: str = ""
    items: list[dict] = field(default_factory=list)
    note: str = ""


@dataclass(slots=True)
class Report:
    query: str
    verdict: str
    confidence: float
    sections: list[ReportSection] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = REPORT_VERSION

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "sections": [
                {"title": s.title, "body": s.body, "items": s.items, "note": s.note}
                for s in self.sections
            ],
            "generated_at": self.generated_at,
            "schema_version": self.schema_version,
        }

    def to_text(self) -> str:
        lines = [f"تقرير: {self.query}", "=" * 60,
                 f"الحكم: {self.verdict}   الثقة: {self.confidence:.2f}", ""]
        for s in self.sections:
            lines.append(f"── {s.title} ──")
            if s.body:
                lines.append(s.body)
            for item in s.items:
                lines.append("  • " + str(item.get("line", item)))
            if s.note:
                lines.append(f"  ملاحظة: {s.note}")
            lines.append("")
        return "\n".join(lines)


class ReportBuilder:
    """يبني التقرير من نتيجة خط الأنابيب."""

    def __init__(self, *, max_evidence: int = 8):
        self.max_evidence = int(max_evidence)
        self.version = REPORT_VERSION

    def build(self, pipeline_result: dict) -> Report:
        answer = pipeline_result.get("answer", {}) or {}
        verification = pipeline_result.get("verification", {}) or {}
        evidence = pipeline_result.get("evidence", {}) or {}

        report = Report(
            query=str(pipeline_result.get("query", "")),
            verdict=str(verification.get("verdict", answer.get("verdict", "unknown"))),
            confidence=float(verification.get("confidence", 0.0) or 0.0),
        )

        # 1) الخلاصة
        if answer.get("answered"):
            n = len(answer.get("citations", []))
            report.sections.append(ReportSection(
                "الخلاصة",
                f"وُجدت {n} شواهد موثّقة تجيب عن السؤال.",
                note="النص المعروض مقتطع من مصدره حرفياً؛ راجع الأصل للاستشهاد.",
            ))
        else:
            report.sections.append(ReportSection(
                "الخلاصة",
                "لم تكف الأدلة لإجابة موثّقة.",
                note=str(answer.get("refusal_reason", "")),
            ))

        # 2) الأدلة
        citations = answer.get("citations", [])[: self.max_evidence]
        if citations:
            report.sections.append(ReportSection(
                "الأدلة الموثّقة",
                items=[
                    {
                        "line": f"{c.get('citation','')} — {(c.get('text') or '')[:150]}",
                        "citation": c.get("citation"),
                        "element_id": c.get("element_id"),
                        "hadith_number": c.get("hadith_number"),
                        "quality": c.get("quality"),
                    }
                    for c in citations
                ],
            ))

        # 3) سلسلة الرواة
        narrators = pipeline_result.get("narrators", []) or []
        if narrators:
            resolved = [n for n in narrators
                        if n.get("resolution") in ("exact", "alias")]
            unknown = [n for n in narrators if n.get("resolution") == "unresolved"]
            report.sections.append(ReportSection(
                "الرواة",
                f"{len(resolved)} راوياً مربوطاً من {len(narrators)}.",
                items=[
                    {"line": f"{n.get('canonical_name') or n.get('query')} "
                             f"({n.get('resolution')}، ورد {n.get('occurrences',1)} مرة)"}
                    for n in narrators[:10]
                ],
                note=(f"{len(unknown)} اسماً غير مسجَّل — يُضاف بمراجعتك"
                      if unknown else ""),
            ))

        # 4) التعارضات — تُعرض ولا يُحكم فيها
        conflicts = verification.get("conflicts", []) or []
        if conflicts:
            report.sections.append(ReportSection(
                "تعارضات ظاهرة",
                "وُجد تعارض بين الشواهد. لا يرجّح النظام بينها.",
                items=[{"line": c} for c in conflicts],
                note="الترجيح بين المتعارضات عمل المحقق لا الآلة.",
            ))

        # 5) ما يحتاج مراجعة
        missing = verification.get("missing", []) or []
        rejected = evidence.get("rejected", []) or []
        if missing or rejected:
            items = [{"line": m} for m in missing]
            items += [
                {"line": f"عنصر {r.get('element_id')} استُبعد: {r.get('reason')}"}
                for r in rejected[:5]
            ]
            report.sections.append(ReportSection("ما يحتاج مراجعة", items=items))

        # 6) التفسير
        checks = verification.get("checks", []) or []
        if checks:
            report.sections.append(ReportSection(
                "أساس الحكم",
                items=[
                    {"line": f"{c.get('name')}: {c.get('detail')} "
                             f"({'اجتاز' if c.get('passed') else 'لم يجتز'})"}
                    for c in checks
                ],
            ))

        # 7) الشفافية التشغيلية
        trace = pipeline_result.get("trace", []) or []
        if trace:
            report.sections.append(ReportSection(
                "مسار المعالجة",
                items=[
                    {"line": f"{s.get('stage')}: "
                             f"{'تُخطّي — ' + str(s.get('reason')) if s.get('skipped') else str(s.get('ms')) + 'ms'}"}
                    for s in trace
                ],
            ))

        return report


__all__ = ["REPORT_VERSION", "Report", "ReportBuilder", "ReportSection"]
