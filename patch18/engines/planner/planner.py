"""
Planner Engine — القسم 8: "اختيار المسار الأقل تكلفة والأعلى دقة".

المشكلة التي يحلّها
-------------------
كل استعلام كان يمرّ على المسارات الثلاثة كاملةً مهما كان شكله.
فالبحث الدلالي يعمل على كلمة "الله" — وهو عبث: كلمة واحدة شائعة لا
دلالة مميّزة لها، والنتائج الستون التي يرجّعها تُقصى كلها من العشرين
الأولى فتضيف زمناً بلا فائدة.

الخطة تُبنى من **النية** ودرجة ثقتها:

    narrator  -> نصي دقيق + قاموس رواة؛ الدلالي بلا قيمة للأعلام
    concept   -> الدلالي أساسي؛ المفهوم لا يُطابَق حرفياً
    citation  -> نصي فقط؛ الرقم يُطابَق أو لا
    general منخفض الثقة -> نصي فقط، مع طلب توضيح

schema_version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

PLANNER_VERSION = "1.0.0"


class Route(str, Enum):
    FTS = "fts"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    GAZETTEER = "gazetteer"
    GRAPH = "graph"


@dataclass(slots=True)
class QueryPlan:
    routes: list[Route]
    weights: dict[str, float] = field(default_factory=dict)
    limit_per_route: int = 100
    max_time_ms: int = 5000
    ask_clarification: bool = False
    clarification: str = ""
    reasons: list[str] = field(default_factory=list)
    schema_version: str = PLANNER_VERSION

    def as_dict(self) -> dict:
        return {
            "routes": [r.value for r in self.routes],
            "weights": self.weights,
            "limit_per_route": self.limit_per_route,
            "max_time_ms": self.max_time_ms,
            "ask_clarification": self.ask_clarification,
            "clarification": self.clarification,
            "reasons": self.reasons,
            "schema_version": self.schema_version,
        }


# خرائط المسارات لكل نية، مع أوزانها
_PLANS: dict[str, tuple[list[Route], dict[str, float], str]] = {
    "narrator": (
        [Route.FTS, Route.FUZZY, Route.GAZETTEER],
        {"fts": 1.0, "fuzzy": 0.9, "gazetteer": 1.2},
        "الأعلام تُطابَق حرفياً؛ الدلالي لا يميّز بين اسمين متقاربين",
    ),
    "isnad": (
        [Route.FTS, Route.FUZZY, Route.GAZETTEER, Route.GRAPH],
        {"fts": 1.0, "fuzzy": 1.0, "gazetteer": 1.1, "graph": 1.0},
        "السلسلة بنية علاقات، فيدخل الرسم البياني",
    ),
    "hadith": (
        [Route.FTS, Route.FUZZY, Route.SEMANTIC],
        {"fts": 1.0, "fuzzy": 0.9, "semantic": 0.8},
        "المتن يُطابَق لفظاً ومعنى معاً",
    ),
    "chapter": (
        [Route.FTS],
        {"fts": 1.2},
        "العنوان يُطابَق حرفياً",
    ),
    "ruling": (
        [Route.FTS, Route.SEMANTIC],
        {"fts": 0.9, "semantic": 1.1},
        "السؤال الحكمي يحتاج فهم المعنى",
    ),
    "concept": (
        [Route.SEMANTIC, Route.FTS],
        {"semantic": 1.3, "fts": 0.7},
        "المفهوم لا يُطابَق حرفياً",
    ),
    "citation": (
        [Route.FTS],
        {"fts": 1.3},
        "الموضع رقم يُطابَق أو لا",
    ),
}


class Planner:
    """
    يبني خطة الاستعلام.

    Circuit breaker مضمَّن (القسم 9): سقف زمني وسقف نتائج لكل مسار،
    فلا استعلام يستنزف النظام.
    """

    def __init__(self, *, max_time_ms: int = 5000, limit_per_route: int = 100):
        self.max_time_ms = int(max_time_ms)
        self.limit_per_route = int(limit_per_route)
        self.version = PLANNER_VERSION

    def plan(
        self, query: str, intent_label: str, intent_confidence: float
    ) -> QueryPlan:
        words = len((query or "").split())
        reasons: list[str] = []

        if intent_confidence < 0.4:
            # نية غير واضحة: أرخص مسار، مع طلب توضيح
            clarification = (
                "كلمة واحدة شائعة — أتقصد راوياً؟ أم متن حديث؟ أم باباً؟"
                if words <= 1
                else "النية غير محددة — وضّح ما تبحث عنه"
            )
            return QueryPlan(
                [Route.FTS], {"fts": 1.0},
                min(self.limit_per_route, 50), self.max_time_ms,
                True, clarification,
                [f"ثقة النية {intent_confidence:.2f} دون العتبة",
                 "المسار الدلالي أُلغي: لا يفيد مع سؤال غير محدد"],
            )

        routes, weights, why = _PLANS.get(
            intent_label,
            ([Route.FTS, Route.FUZZY], {"fts": 1.0, "fuzzy": 0.9},
             "خطة افتراضية"),
        )
        reasons.append(why)

        if Route.SEMANTIC not in routes:
            reasons.append("المسار الدلالي مستبعَد عمداً لهذه النية")
        if words <= 2 and Route.SEMANTIC in routes:
            routes = [r for r in routes if r is not Route.SEMANTIC]
            reasons.append("استعلام قصير: الدلالي بلا قيمة تمييزية")

        return QueryPlan(
            list(routes), dict(weights), self.limit_per_route,
            self.max_time_ms, False, "", reasons,
        )


__all__ = ["PLANNER_VERSION", "Planner", "QueryPlan", "Route"]
