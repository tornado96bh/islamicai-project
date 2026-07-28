"""
Temporal Reasoning — الاستدلال الزمني.

السؤال الذي يجيبه: **هل أدرك هذا الراوي ذاك؟**

وهو سؤال حاسم في نقد الأسانيد: سندٌ فيه راوٍ يروي عمّن مات قبل
ولادته سندٌ منقطع، مهما بدا متصلاً في النص.

المنهج
------
لا يُحكم بالانقطاع جزماً عند نقص التواريخ — يُرجَّع `unknown` مع
سببه. الحكم بلا بيانات أسوأ من الامتناع.

والتقدير حين تُعرف الوفاة وحدها: يُفترض عمر معقول (نحو سبعين سنة)
ويُصرَّح بأنه تقدير لا يقين.

schema_version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

TEMPORAL_VERSION = "1.0.0"

# افتراضات معلنة لا مخفية
ASSUMED_LIFESPAN = 70          # سنة، عند غياب الميلاد
MIN_LEARNING_AGE = 10          # أدنى سنّ يُعتدّ بسماعه
MIN_OVERLAP_YEARS = 5          # أدنى تعاصر يُعتدّ به


class Contemporaneity(str, Enum):
    CERTAIN = "certain"          # تعاصر مؤكد
    LIKELY = "likely"            # مرجَّح بتقدير
    IMPOSSIBLE = "impossible"    # مستحيل — انقطاع
    UNKNOWN = "unknown"          # لا بيانات


@dataclass(slots=True)
class TemporalVerdict:
    relation: Contemporaneity
    overlap_years: int | None = None
    reason: str = ""
    assumptions: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.assumptions is None:
            self.assumptions = []

    def as_dict(self) -> dict:
        return {"relation": self.relation.value, "overlap_years": self.overlap_years,
                "reason": self.reason, "assumptions": self.assumptions}


@dataclass(slots=True)
class Lifespan:
    name: str
    birth: int | None = None     # هجري
    death: int | None = None

    def estimated_birth(self) -> tuple[int | None, bool]:
        """يرجّع (السنة، هل هي تقدير)."""
        if self.birth is not None:
            return self.birth, False
        if self.death is not None:
            return self.death - ASSUMED_LIFESPAN, True
        return None, False

    def estimated_death(self) -> tuple[int | None, bool]:
        if self.death is not None:
            return self.death, False
        if self.birth is not None:
            return self.birth + ASSUMED_LIFESPAN, True
        return None, False


class TemporalReasoner:
    """يحكم على إمكان اللقاء بين راويين."""

    def __init__(self, *, assumed_lifespan: int = ASSUMED_LIFESPAN):
        self.assumed_lifespan = int(assumed_lifespan)
        self.version = TEMPORAL_VERSION

    def can_meet(self, student: Lifespan, teacher: Lifespan) -> TemporalVerdict:
        """
        هل يمكن أن يسمع التلميذُ من الشيخ؟

        الترتيب مقصود: التلميذ أولاً لأن السؤال عن سماعه، لا عن
        مجرد التعاصر.
        """
        assumptions: list[str] = []

        s_birth, s_birth_est = student.estimated_birth()
        s_death, s_death_est = student.estimated_death()
        t_death, t_death_est = teacher.estimated_death()
        t_birth, _ = teacher.estimated_birth()

        if s_birth is None or t_death is None:
            missing = []
            if s_birth is None:
                missing.append(f"لا تاريخ لـ {student.name}")
            if t_death is None:
                missing.append(f"لا تاريخ لـ {teacher.name}")
            return TemporalVerdict(
                Contemporaneity.UNKNOWN, None, "؛ ".join(missing),
                ["لا يُحكم بالانقطاع عند نقص التواريخ"],
            )

        if s_birth_est:
            assumptions.append(f"ميلاد {student.name} مقدَّر (وفاته ناقص {self.assumed_lifespan})")
        if t_death_est:
            assumptions.append(f"وفاة {teacher.name} مقدَّرة")

        # أدنى سنّ للسماع
        earliest_hearing = s_birth + MIN_LEARNING_AGE
        if earliest_hearing > t_death:
            gap = earliest_hearing - t_death
            return TemporalVerdict(
                Contemporaneity.IMPOSSIBLE, 0,
                f"{student.name} بلغ سنّ السماع بعد وفاة {teacher.name} بـ{gap} سنة",
                assumptions,
            )

        # نافذة التعاصر
        start = max(earliest_hearing, t_birth + MIN_LEARNING_AGE if t_birth else earliest_hearing)
        end = min(s_death or t_death, t_death)
        overlap = max(0, end - start)

        if overlap < MIN_OVERLAP_YEARS:
            return TemporalVerdict(
                Contemporaneity.UNKNOWN, overlap,
                f"تعاصر {overlap} سنة فقط — دون العتبة",
                assumptions + [f"عتبة التعاصر {MIN_OVERLAP_YEARS} سنوات"],
            )

        certain = not (s_birth_est or t_death_est)
        return TemporalVerdict(
            Contemporaneity.CERTAIN if certain else Contemporaneity.LIKELY,
            overlap,
            f"تعاصرا نحو {overlap} سنة",
            assumptions,
        )

    def check_chain(self, chain: list[Lifespan]) -> dict:
        """
        يفحص سلسلة إسناد كاملة.

        السلسلة مرتَّبة من التلميذ إلى الشيخ، كما ترد في السند.
        """
        links: list[dict] = []
        breaks = 0
        unknowns = 0

        for i in range(len(chain) - 1):
            verdict = self.can_meet(chain[i], chain[i + 1])
            links.append({
                "student": chain[i].name,
                "teacher": chain[i + 1].name,
                **verdict.as_dict(),
            })
            if verdict.relation is Contemporaneity.IMPOSSIBLE:
                breaks += 1
            elif verdict.relation is Contemporaneity.UNKNOWN:
                unknowns += 1

        total = max(len(chain) - 1, 1)
        return {
            "links": links,
            "length": len(chain),
            "breaks": breaks,
            "unknowns": unknowns,
            "continuity": round((total - breaks - unknowns * 0.5) / total, 4),
            "verdict": (
                "منقطع" if breaks else
                "غير محسوم" if unknowns > total / 2 else
                "متصل ظاهراً"
            ),
        }


__all__ = ["ASSUMED_LIFESPAN", "TEMPORAL_VERSION", "Contemporaneity",
           "Lifespan", "TemporalReasoner", "TemporalVerdict"]
