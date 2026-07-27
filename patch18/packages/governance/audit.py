"""
الحوكمة — القسم 9 من المواصفة.

RBAC + Audit Log + Circuit Breakers في وحدة واحدة، لأنها ثلاثتها
وجوه لمبدأ واحد: **كل قرار قابل للتفسير والتدقيق والرجوع عنه**.

schema_version: 1.0.0
"""

from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

GOVERNANCE_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# RBAC — القسم 9
# ---------------------------------------------------------------------------

class Role(str, Enum):
    GUEST = "guest"          # مستخدم عادي
    RESEARCHER = "researcher"  # باحث / طالب علم
    VERIFIER = "verifier"    # محقق / خبير
    ADMIN = "admin"          # مشرف


class Permission(str, Enum):
    SEARCH = "search"
    VIEW_EVIDENCE = "view_evidence"
    EXPORT = "export"
    PROPOSE_CORRECTION = "propose_correction"
    APPROVE_CORRECTION = "approve_correction"
    MERGE_ENTITIES = "merge_entities"
    REINDEX = "reindex"
    MANAGE_USERS = "manage_users"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.GUEST: frozenset({Permission.SEARCH}),
    Role.RESEARCHER: frozenset({
        Permission.SEARCH, Permission.VIEW_EVIDENCE, Permission.EXPORT,
        Permission.PROPOSE_CORRECTION,
    }),
    Role.VERIFIER: frozenset({
        Permission.SEARCH, Permission.VIEW_EVIDENCE, Permission.EXPORT,
        Permission.PROPOSE_CORRECTION, Permission.APPROVE_CORRECTION,
        Permission.MERGE_ENTITIES,
    }),
    Role.ADMIN: frozenset(Permission),
}


class PermissionDenied(PermissionError):
    """يُرفع مع سبب مكتوب — لا رفض صامت."""


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require_permission(role: Role, permission: Permission) -> None:
    if not has_permission(role, permission):
        raise PermissionDenied(
            f"الدور '{role.value}' لا يملك صلاحية '{permission.value}'"
        )


# ---------------------------------------------------------------------------
# Audit Log — القسم 9
# ---------------------------------------------------------------------------

class AuditAction(str, Enum):
    SEARCH = "search"
    EVIDENCE_BUILT = "evidence_built"
    VERIFICATION = "verification"
    ANSWER_REFUSED = "answer_refused"
    CORRECTION_PROPOSED = "correction_proposed"
    CORRECTION_APPROVED = "correction_approved"
    ENTITY_MERGED = "entity_merged"
    REINDEX = "reindex"
    MEMORY_INVALIDATED = "memory_invalidated"


@dataclass(slots=True)
class AuditRecord:
    record_id: str
    action: AuditAction
    actor: str
    role: str
    detail: dict = field(default_factory=dict)
    reason: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = GOVERNANCE_VERSION

    def as_dict(self) -> dict:
        return {
            "record_id": self.record_id, "action": self.action.value,
            "actor": self.actor, "role": self.role, "detail": self.detail,
            "reason": self.reason, "at": self.at,
            "schema_version": self.schema_version,
        }


class AuditLog:
    """
    سجلّ لا يُحذف منه.

    الإلحاق فقط: التعديل أو الحذف يُبطل غرض السجلّ. الملف بصيغة
    JSONL ليبقى قابلاً للإلحاق بلا إعادة كتابة.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path("data/audit/audit.jsonl")
        self.records: list[AuditRecord] = []
        self.version = GOVERNANCE_VERSION

    def record(
        self, action: AuditAction, actor: str, role: Role | str,
        detail: dict | None = None, reason: str = "",
    ) -> AuditRecord:
        rec = AuditRecord(
            record_id=uuid.uuid4().hex[:16], action=action, actor=actor,
            role=role.value if isinstance(role, Role) else str(role),
            detail=detail or {}, reason=reason,
        )
        self.records.append(rec)
        return rec

    def flush(self) -> int:
        """يُلحق السجلات بالملف ويفرّغ الذاكرة."""
        if not self.records:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            for rec in self.records:
                fh.write(json.dumps(rec.as_dict(), ensure_ascii=False) + "\n")
        n = len(self.records)
        self.records.clear()
        return n

    def by_action(self, action: AuditAction) -> list[AuditRecord]:
        return [r for r in self.records if r.action is action]


# ---------------------------------------------------------------------------
# Circuit Breakers — القسم 9
# ---------------------------------------------------------------------------

class BudgetExceeded(RuntimeError):
    """تجاوز الميزانية — يُرفع بدل ترك النظام يستنزف نفسه."""


@dataclass(slots=True)
class Budget:
    max_time_ms: int = 5000
    max_results: int = 500
    max_expansions: int = 20
    max_db_calls: int = 60


class CircuitBreaker:
    """
    يفرض ميزانية وقت وعدد على استعلام واحد.

    القسم 9: "منع الحلقات اللانهائية وفرض ميزانية توكن/وقت."
    """

    def __init__(self, budget: Budget | None = None):
        self.budget = budget or Budget()
        self.started = 0.0
        self.results = 0
        self.expansions = 0
        self.db_calls = 0
        self.tripped = False
        self.trip_reason = ""

    @contextmanager
    def guard(self):
        self.started = time.monotonic()
        try:
            yield self
        finally:
            pass

    @property
    def elapsed_ms(self) -> float:
        return (time.monotonic() - self.started) * 1000 if self.started else 0.0

    def _trip(self, reason: str) -> None:
        self.tripped = True
        self.trip_reason = reason
        raise BudgetExceeded(reason)

    def check_time(self) -> None:
        if self.elapsed_ms > self.budget.max_time_ms:
            self._trip(f"تجاوز الزمن: {self.elapsed_ms:.0f}ms")

    def add_results(self, n: int) -> None:
        self.results += n
        if self.results > self.budget.max_results:
            self._trip(f"تجاوز عدد النتائج: {self.results}")

    def add_expansion(self, n: int = 1) -> None:
        self.expansions += n
        if self.expansions > self.budget.max_expansions:
            self._trip(f"تجاوز توسيع الاستعلام: {self.expansions}")

    def add_db_call(self, n: int = 1) -> None:
        self.db_calls += n
        if self.db_calls > self.budget.max_db_calls:
            self._trip(f"تجاوز نداءات القاعدة: {self.db_calls}")

    def stats(self) -> dict:
        return {
            "elapsed_ms": round(self.elapsed_ms, 1), "results": self.results,
            "expansions": self.expansions, "db_calls": self.db_calls,
            "tripped": self.tripped, "trip_reason": self.trip_reason,
        }


__all__ = [
    "GOVERNANCE_VERSION", "ROLE_PERMISSIONS", "AuditAction", "AuditLog",
    "AuditRecord", "Budget", "BudgetExceeded", "CircuitBreaker",
    "Permission", "PermissionDenied", "Role", "has_permission",
    "require_permission",
]
