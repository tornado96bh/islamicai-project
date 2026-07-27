"""
سجلّ المحركات — الحالة الصادقة لكل طبقة من الأربع والعشرين.

لماذا هذا الملف موجود
---------------------
طُلب بناء المحركات كلها دفعةً واحدة. الصادق أن يُقال: بعضها يعمل
مقيساً، وبعضها هيكل بعقد ثابت بلا تنفيذ، وبعضها يحتاج بياناتٍ لا
يملكها إلا صاحب المشروع (قائمة رواة، تصنيف مفاهيمي، أسئلة محكَّمة).

فبدل ادعاء الاكتمال، هذا السجلّ **يُصرّح** بحالة كل محرك، ويُستعمل
برمجياً: أي مسار يطلب محركاً غير جاهز يحصل على رفض واضح بسببه، لا
على نتيجة صامتة مضلِّلة.

    from packages.engines.registry import require_engine
    require_engine("verifier")   # -> EngineNotReady بسبب مكتوب

schema_version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

REGISTRY_VERSION = "1.0.0"


class Status(str, Enum):
    READY = "ready"              # يعمل ومقيس على بيانات حقيقية
    PARTIAL = "partial"          # يعمل جزئياً، بحدود معلومة
    CONTRACT_ONLY = "contract"   # العقد مكتوب، لا تنفيذ
    NEEDS_DATA = "needs_data"    # التنفيذ ممكن، البيانات ناقصة
    NOT_STARTED = "not_started"


class EngineNotReady(RuntimeError):
    """يُرفع حين يُطلب محرك غير جاهز — بدل إرجاع نتيجة مضلِّلة."""


@dataclass(slots=True)
class Engine:
    key: str
    name_ar: str
    status: Status
    layer: int
    module: str = ""
    note: str = ""
    blocked_by: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


ENGINES: dict[str, Engine] = {
    e.key: e
    for e in [
        # ---- الطبقات العاملة -------------------------------------
        Engine("normalizer", "التطبيع العربي", Status.READY, 2,
               "packages.learning.dictionary",
               "أربع طبقات نصية، خريطة إزاحة محفوظة",
               metrics={"tests": 32}),
        Engine("diacritics", "الحركات والهمزات والجذور", Status.READY, 6,
               "packages.arabic.diacritics",
               "يميّز عَلَم من عِلْم، ويوحّد مسؤول ومسئول",
               metrics={"match_cases": "6/6"}),
        Engine("ocr_corrector", "تصحيح OCR", Status.READY, 3,
               "packages.ingestion.ocr_corrector",
               "65,655 تمديد أُزيل، لحم عبر الترقيم",
               metrics={"merges": 2899}),
        Engine("layout", "تحليل بنية الصفحة", Status.READY, 25,
               "packages.layout.classifier",
               "متن/سند/هامش/ترويسة/عنوان",
               metrics={"tests": 30}),
        Engine("hadith_splitter", "تفكيك الرواية", Status.PARTIAL, 14,
               "packages.layout.hadith_splitter",
               "رقم/سند/متن. 216 رواية مفكَّكة من 13,916 عنصراً",
               blocked_by=["جودة OCR في بقية العناصر"]),
        Engine("intent", "تصنيف النية", Status.READY, 54,
               "packages.search.intent_v2",
               "أدلة موزونة وثقة مفسَّرة",
               metrics={"avg_confidence": 0.84}),
        Engine("fts", "البحث النصي", Status.READY, 19, "packages.search.fts"),
        Engine("fuzzy", "البحث التقريبي", Status.READY, 36, "packages.search.fuzzy"),
        Engine("ranking", "الترتيب والدمج", Status.READY, 51,
               "packages.search.ranking",
               "RRF مع ست إشارات متدرّجة وشرح كامل"),
        Engine("entity_filter", "ترشيح الكيانات", Status.READY, 8,
               "packages.learning.entity_filter"),
        Engine("contracts", "العقود", Status.READY, 0,
               "packages.schemas.contracts", "21 عقداً"),

        # ---- تعمل جزئياً ------------------------------------------
        Engine("semantic", "البحث الدلالي", Status.PARTIAL, 18,
               "packages.learning.embeddings_v2",
               "النموذج الحقيقي مثبَّت (6/6 على أزواج عربية) لكن "
               "الفهرس ما زال 256 بُعداً؛ يحتاج إعادة فهرسة Qdrant",
               blocked_by=["إعادة بناء المتجهات بـ384 بُعداً"]),
        Engine("entity_extraction", "استخراج الكيانات", Status.PARTIAL, 8,
               "packages.learning.entities",
               "قواعد بنيوية لا نموذج NER"),

        # ---- تحتاج بيانات منك --------------------------------------
        Engine("narrator_resolver", "ربط الرواة", Status.NEEDS_DATA, 15,
               note="يحتاج قائمة رواة معتمدة بمعرّفات وكنى وطبقات",
               blocked_by=["gazetteer الرواة"]),
        Engine("isnad_graph", "رسم الأسانيد", Status.NEEDS_DATA, 49,
               note="التفكيك يعمل؛ بناء الرسم يحتاج رواة مربوطين",
               blocked_by=["narrator_resolver"]),
        Engine("ontology", "التصنيف المفاهيمي", Status.NEEDS_DATA, 50,
               note="طهارة/وضوء/غسل/تيمم — يحتاج شجرة مفاهيم منك",
               blocked_by=["تصنيف مفاهيمي"]),
        Engine("golden_eval", "القياس المحكَّم", Status.NEEDS_DATA, 58,
               "scripts/build_golden.py",
               "12 سؤالاً مسجَّلاً، صفر محكَّم بمعرّفات",
               blocked_by=["20 سؤالاً محكَّماً"]),

        # ---- عقود بلا تنفيذ ----------------------------------------
        Engine("evidence_bundle", "حزمة الأدلة", Status.CONTRACT_ONLY, 23,
               "packages.schemas.contracts:EvidenceBundle",
               "العقد مكتوب ومُختبَر؛ ينقص خط الأنابيب الذي يبنيه من "
               "أعلى النتائج مع التخطيط والسند والمتن",
               blocked_by=["خط أنابيب البناء"]),
        Engine("verifier", "التحقق", Status.CONTRACT_ONLY, 24,
               "packages.schemas.contracts:VerificationResult",
               blocked_by=["evidence_bundle"]),
        Engine("final_answer", "الإجابة الموثّقة", Status.CONTRACT_ONLY, 23,
               "packages.schemas.contracts:FinalAnswer",
               "يرفض الإجابة بلا مصدر — العقد جاهز",
               blocked_by=["verifier"]),

        # ---- لم تبدأ -----------------------------------------------
        Engine("knowledge_graph", "شبكة المعرفة", Status.NOT_STARTED, 20,
               blocked_by=["ontology", "narrator_resolver"]),
        Engine("cross_encoder", "إعادة الترتيب العميق", Status.NOT_STARTED, 51,
               note="BAAI/bge-reranker — أيام عمل، لكن بلا قياس لن نعرف إن حسّن",
               blocked_by=["golden_eval"]),
        Engine("morphology", "التحليل الصرفي", Status.NOT_STARTED, 5,
               note="CAMeL Tools؛ الجذع الخفيف موجود كبديل مؤقت"),
        Engine("coreference", "ربط الإحالات", Status.NOT_STARTED, 32,
               blocked_by=["morphology"]),
        Engine("contradiction", "كشف التعارض", Status.NOT_STARTED, 41,
               blocked_by=["knowledge_graph"]),
        Engine("worker", "المشغّل والمجدول", Status.NOT_STARTED, 60,
               note="إعادة الفهرسة والاستيعاب تعمل يدوياً بالسكربتات؛ "
                    "الجدولة تحتاج بنية تشغيل مستقلة"),
        Engine("audit", "سجلّ التدقيق و RBAC", Status.NOT_STARTED, 60,
               note="score_explain يوفّر تفسير الترتيب؛ سجلّ التدقيق "
                    "الكامل والصلاحيات يحتاجان طبقة مستخدمين أولاً",
               blocked_by=["طبقة المستخدمين"]),
    ]
}


def get_engine(key: str) -> Engine | None:
    return ENGINES.get(key)


def require_engine(key: str) -> Engine:
    """
    يرجّع المحرك إن كان جاهزاً، وإلا يرفع خطأً **بسببه**.

    الفشل الصريح هنا مقصود: النتيجة الصامتة من محرك ناقص أخطر من
    غيابه، لأنها تبدو صحيحة.
    """
    engine = ENGINES.get(key)
    if engine is None:
        raise EngineNotReady(f"لا محرك بهذا المفتاح: {key}")
    if engine.status in (Status.READY, Status.PARTIAL):
        return engine
    blockers = "، ".join(engine.blocked_by) if engine.blocked_by else "لم يبدأ"
    raise EngineNotReady(
        f"المحرك '{engine.name_ar}' حالته {engine.status.value}. المعوّق: {blockers}"
    )


def summary() -> dict[str, int]:
    out: dict[str, int] = {}
    for e in ENGINES.values():
        out[e.status.value] = out.get(e.status.value, 0) + 1
    return out


def blocked_by_user() -> list[Engine]:
    """المحركات التي تنتظر بياناتٍ من صاحب المشروع وحده."""
    return [e for e in ENGINES.values() if e.status is Status.NEEDS_DATA]


def report() -> str:
    lines = ["سجلّ المحركات", "=" * 62]
    order = [Status.READY, Status.PARTIAL, Status.NEEDS_DATA,
             Status.CONTRACT_ONLY, Status.NOT_STARTED]
    titles = {
        Status.READY: "جاهزة ومقيسة",
        Status.PARTIAL: "تعمل جزئياً",
        Status.NEEDS_DATA: "تنتظر بياناتك",
        Status.CONTRACT_ONLY: "عقد بلا تنفيذ",
        Status.NOT_STARTED: "لم تبدأ",
    }
    for status in order:
        group = [e for e in ENGINES.values() if e.status is status]
        if not group:
            continue
        lines.append(f"\n{titles[status]}  ({len(group)})")
        for e in sorted(group, key=lambda x: x.layer):
            lines.append(f"  [{e.layer:>2}] {e.name_ar}")
            if e.note:
                lines.append(f"       {e.note}")
            if e.blocked_by:
                lines.append(f"       معوّق بـ: {'، '.join(e.blocked_by)}")
    return "\n".join(lines)


__all__ = [
    "ENGINES", "REGISTRY_VERSION", "Engine", "EngineNotReady", "Status",
    "blocked_by_user", "get_engine", "report", "require_engine", "summary",
]
