"""
مسارات خط الأنابيب الموحَّد.

منفصلة عن `/search` القائم عمداً: البحث القديم يبقى كما هو، ويُضاف
المسار الموثَّق بجانبه. فمن أراد النتائج الخام أخذها، ومن أراد
الإجابة الموثَّقة أخذها، بلا كسر أي مستهلك قائم.

    GET /pipeline/ask      الخط كاملاً: نية -> خطة -> أدلة -> تحقق -> إجابة
    GET /pipeline/report   نفسه بصيغة تقرير مقروء
    GET /pipeline/engines  حالة المحركات
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.app.deps import db_session

router = APIRouter()


@router.get("/ask")
def ask(
    q: str = Query(..., min_length=1, description="السؤال"),
    limit: int = Query(20, ge=1, le=100),
    use_memory: bool = Query(True, description="استعمال الذاكرة المؤكَّدة"),
    actor: str = Query("anonymous"),
    role: str = Query("researcher"),
    db: Session = Depends(db_session),
):
    """
    الخط كاملاً.

    يرجّع الإجابة الموثَّقة **أو** الامتناع المعلَّل، مع مسار
    المعالجة كاملاً في `trace` فيمكن تفسير أي نتيجة.
    """
    try:
        from engines.pipeline.orchestrator import Pipeline
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "حزمة engines غير مثبَّتة. شغّل: pip install -e . "
                f"({exc})"
            ),
        ) from exc

    result = Pipeline(db, actor=actor, role=role, use_memory=use_memory).run(
        q, limit=limit
    )
    return result.as_dict()


@router.get("/report")
def report(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    fmt: str = Query("json", pattern="^(json|text)$"),
    db: Session = Depends(db_session),
):
    """تقرير شامل: خلاصة، أدلة، رواة، تعارضات، ما يحتاج مراجعة."""
    try:
        from engines.pipeline.orchestrator import Pipeline
        from engines.report.builder import ReportBuilder
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    payload = Pipeline(db).run(q, limit=limit).as_dict()
    built = ReportBuilder().build(payload)
    if fmt == "text":
        return {"query": q, "report": built.to_text()}
    return built.as_dict()


@router.get("/engines")
def engines():
    """حالة المحركات — ما يعمل وما ينتظر بيانات وما لم يبدأ."""
    try:
        from packages.engines.registry import ENGINES, summary

        return {
            "summary": summary(),
            "engines": [
                {
                    "key": e.key, "name": e.name_ar, "status": e.status.value,
                    "layer": e.layer, "note": e.note, "blocked_by": e.blocked_by,
                }
                for e in sorted(ENGINES.values(), key=lambda x: x.layer)
            ],
        }
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
