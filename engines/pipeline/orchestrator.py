"""
خط الأنابيب الموحَّد — ربط المحركات كلها.

موقعه في المواصفة
-----------------
القسم 6.2 (مسار الاستعلام):
    فهم السؤال -> توسيع -> استرجاع هجين -> إعادة ترتيب ->
    بناء Evidence Bundle -> التحقق -> إجابة موثقة أو إحالة

كانت المحركات مبنيةً مختبَرةً لكن **مستقلة**، فلا يراها أحد في
مسار البحث. هذا الملف هو الوصلة الواحدة التي تجمعها.

الترتيب مقصود
-------------
    1. Intent      تُحدَّد النية بثقة محسوبة
    2. Planner     تُختار المسارات — لا بحث دلالي لسؤال غامض
    3. Search      استرجاع + ترتيب (المحرك القائم)
    4. Entities    ترشيح وتوحيد المرشحين
    5. Narrator    ربط أسماء السند بكيانات
    6. Evidence    بناء الحزمة الموثّقة
    7. Verifier    التحقق أو الامتناع
    8. Answer      إجابة باستشهادات، أو رفض معلَّل
    9. Memory      تخزين المؤكَّد وحده
   10. Audit       تسجيل القرار وسببه

وكل خطوة تُسجَّل في `trace` فيمكن تفسير أي نتيجة خطوةً خطوة.

schema_version: 1.0.0
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

PIPELINE_VERSION = "1.0.0"


@dataclass(slots=True)
class Stage:
    name: str
    ms: float
    detail: dict = field(default_factory=dict)
    skipped: bool = False
    reason: str = ""


@dataclass(slots=True)
class PipelineResult:
    query: str
    intent: dict = field(default_factory=dict)
    plan: dict = field(default_factory=dict)
    search: dict = field(default_factory=dict)
    entities: list[dict] = field(default_factory=list)
    narrators: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    answer: dict = field(default_factory=dict)
    trace: list[Stage] = field(default_factory=list)
    from_memory: bool = False
    total_ms: float = 0.0
    schema_version: str = PIPELINE_VERSION

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "intent": self.intent,
            "plan": self.plan,
            "results": self.search.get("results", []),
            "source_counts": self.search.get("source_counts", {}),
            "entity_suggestions": self.entities,
            "narrators": self.narrators,
            "evidence": self.evidence,
            "verification": self.verification,
            "answer": self.answer,
            "trace": [
                {"stage": s.name, "ms": round(s.ms, 1), "skipped": s.skipped,
                 "reason": s.reason, **({"detail": s.detail} if s.detail else {})}
                for s in self.trace
            ],
            "from_memory": self.from_memory,
            "total_ms": round(self.total_ms, 1),
            "pipeline_version": self.schema_version,
        }


class Pipeline:
    """
    المنسّق.

    كل محرك اختياري: إن تعذّر استيراده تُتخطّى خطوته **مع تسجيل
    السبب** — فالنظام يعمل ناقصاً ويقول أين نقص، ولا ينهار ولا
    يُخفي.
    """

    def __init__(
        self,
        db: Any,
        *,
        actor: str = "anonymous",
        role: str = "researcher",
        use_memory: bool = True,
    ):
        self.db = db
        self.actor = actor
        self.role = role
        self.use_memory = use_memory
        self.version = PIPELINE_VERSION
        self._gazetteer = None

    # -----------------------------------------------------------------
    def run(self, query: str, *, limit: int = 20) -> PipelineResult:
        started = time.monotonic()
        out = PipelineResult(query=query)

        def stage(name: str, t0: float, **detail) -> None:
            out.trace.append(Stage(name, (time.monotonic() - t0) * 1000, detail))

        def skip(name: str, reason: str) -> None:
            out.trace.append(Stage(name, 0.0, skipped=True, reason=reason))

        # --- 1) النية -------------------------------------------------
        t0 = time.monotonic()
        try:
            from packages.search.intent_v2 import detect_intent

            intent = detect_intent(query)
            out.intent = intent.as_dict()
            stage("intent", t0, label=intent.label,
                  confidence=round(intent.confidence, 3))
        except Exception as exc:
            skip("intent", f"تعذّر: {exc}")
            out.intent = {"label": "general", "confidence": 0.0}

        label = str(out.intent.get("label", "general"))
        conf = float(out.intent.get("confidence", 0.0) or 0.0)

        # --- 2) الخطة -------------------------------------------------
        t0 = time.monotonic()
        try:
            from engines.planner.planner import Planner

            plan = Planner().plan(query, label, conf)
            out.plan = plan.as_dict()
            stage("planner", t0, routes=[r.value for r in plan.routes])
        except Exception as exc:
            skip("planner", f"تعذّر: {exc}")

        # --- 3) الذاكرة ------------------------------------------------
        versions = self._versions()
        if self.use_memory:
            t0 = time.monotonic()
            try:
                from engines.memory.memory import MemoryEngine

                hit = MemoryEngine().recall(query, label, versions)
                if hit is not None:
                    out.from_memory = True
                    out.answer = hit.payload
                    stage("memory", t0, recalled=True)
                    out.total_ms = (time.monotonic() - started) * 1000
                    return out
                stage("memory", t0, recalled=False)
            except Exception as exc:
                skip("memory", f"تعذّر: {exc}")

        # --- 4) البحث --------------------------------------------------
        t0 = time.monotonic()
        from packages.search.engine import SearchEngine

        payload = SearchEngine(self.db).search(query, limit=limit)
        out.search = payload
        stage("search", t0, results=len(payload.get("results", [])))

        # --- 5) الكيانات: ترشيح وتوحيد ----------------------------------
        t0 = time.monotonic()
        try:
            from packages.learning.entity_dedup import deduplicate

            raw = payload.get("entity_suggestions", []) or []
            out.entities = deduplicate(raw)
            stage("entities", t0, before=len(raw), after=len(out.entities))
        except Exception as exc:
            skip("entities", f"تعذّر: {exc}")
            out.entities = payload.get("entity_suggestions", []) or []

        # --- 6) ربط الرواة ----------------------------------------------
        t0 = time.monotonic()
        try:
            out.narrators = self._resolve_narrators(payload)
            resolved = sum(1 for n in out.narrators if n.get("resolution") in
                           ("exact", "alias"))
            stage("narrator", t0, seen=len(out.narrators), resolved=resolved)
        except Exception as exc:
            skip("narrator", f"تعذّر: {exc}")

        # --- 7) حزمة الأدلة ---------------------------------------------
        t0 = time.monotonic()
        from engines.evidence.bundle import EvidenceBuilder

        merged = dict(payload)
        merged["intent"] = out.intent
        bundle = EvidenceBuilder().build(merged)
        out.evidence = bundle.as_dict()
        stage("evidence", t0, citable=len(bundle.citable),
              distinct=bundle.distinct_sources)

        # --- 8) التحقق ---------------------------------------------------
        t0 = time.monotonic()
        from engines.evidence.verifier import Verifier, compose

        result = Verifier().verify(bundle)
        out.verification = result.as_dict()
        stage("verifier", t0, verdict=result.verdict.value,
              confidence=round(result.confidence, 3))

        # --- 9) الإجابة ---------------------------------------------------
        t0 = time.monotonic()
        answer = compose(bundle, result)
        out.answer = answer.as_dict()
        stage("answer", t0, answered=answer.answered,
              citations=len(answer.citations))

        # --- 10) الذاكرة والتدقيق ------------------------------------------
        if self.use_memory and answer.answered:
            try:
                from engines.memory.memory import MemoryEngine

                mem = MemoryEngine()
                if mem.remember(query, label, result.verdict.value,
                                result.confidence, out.answer, versions):
                    mem.save()
            except Exception:
                pass

        try:
            from packages.governance.audit import AuditAction, AuditLog

            log = AuditLog()
            log.record(
                AuditAction.SEARCH if answer.answered else AuditAction.ANSWER_REFUSED,
                self.actor, self.role,
                {"query": query, "verdict": result.verdict.value},
                answer.refusal_reason,
            )
            log.flush()
        except Exception:
            pass

        out.total_ms = (time.monotonic() - started) * 1000
        return out

    # -----------------------------------------------------------------
    def _resolve_narrators(self, payload: dict) -> list[dict]:
        """يستخرج أسماء السند من النتائج ويربطها بكيانات."""
        from engines.narrator.gazetteer import NarratorGazetteer

        if self._gazetteer is None:
            self._gazetteer = NarratorGazetteer()

        try:
            from packages.layout.hadith_splitter import extract_narrators
        except Exception:
            extract_narrators = None

        seen: dict[str, dict] = {}
        for row in payload.get("results", []):
            isnad = row.get("isnad_text")
            if not isnad:
                continue
            names = (
                extract_narrators(isnad) if extract_narrators
                else [p.strip() for p in isnad.split("،")]
            )
            for name in names:
                if name in seen:
                    seen[name]["occurrences"] += 1
                    continue
                res = self._gazetteer.resolve(name)
                d = res.as_dict()
                d["occurrences"] = 1
                seen[name] = d
        return sorted(seen.values(), key=lambda d: -d["occurrences"])[:20]

    def _versions(self) -> dict[str, str]:
        """بصمة الإصدارات — تُبطل الذاكرة عند أي ترقية."""
        out = {"pipeline": self.version}
        for mod, attr, key in (
            ("packages.ingestion.ocr_corrector", "OCR_CORRECTOR_VERSION", "ocr"),
            ("packages.search.signals", "SIGNALS_VERSION", "signals"),
            ("packages.search.ranking", "RANKING_VERSION", "ranking"),
            ("packages.layout.classifier", "LAYOUT_VERSION", "layout"),
        ):
            try:
                module = __import__(mod, fromlist=[attr])
                out[key] = str(getattr(module, attr, ""))
            except Exception:
                out[key] = "?"
        return out


__all__ = ["PIPELINE_VERSION", "Pipeline", "PipelineResult", "Stage"]
