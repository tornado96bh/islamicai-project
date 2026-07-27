"""
Memory Engine — القسم 8 و 9.

"Memory Engine: تخزين النتائج المؤكدة وإعادة استخدامها."
"Safe Learning: يتعلم النظام التحسينات التشغيلية فقط، لا الحقائق
غير الموثقة."

القاعدة الحاكمة
---------------
لا يُخزَّن إلا ما **اجتاز التحقق**، ولا يُعاد استعماله إلا مع
بصمة إصداره. فإن تغيّر أي إصدار في المسار، سقطت الذاكرة تلقائياً —
لأن نتيجة بُنيت بمصحّح قديم لم تعد صالحة.

وهذا يفرّقها عن الكاش: الكاش يخزّن أي شيء، والذاكرة تخزّن
**المؤكَّد الموثَّق** وحده.

schema_version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

MEMORY_VERSION = "1.0.0"


@dataclass(slots=True)
class MemoryEntry:
    key: str
    query: str
    verdict: str
    confidence: float
    payload: dict
    versions: dict[str, str] = field(default_factory=dict)
    stored_at: float = field(default_factory=time.time)
    hits: int = 0

    def is_valid(self, current_versions: dict[str, str]) -> bool:
        """
        صالحة فقط إن طابقت كل الإصدارات.

        نتيجة بُنيت بمصحّح OCR 1.2.0 لا تصلح بعد ترقيته إلى 1.3.0 —
        وهذا ليس تشدداً: الترقية غيّرت النص نفسه.
        """
        return all(current_versions.get(k) == v for k, v in self.versions.items())


class MemoryEngine:
    """ذاكرة النتائج المؤكَّدة."""

    MIN_CONFIDENCE = 0.7
    ACCEPTED_VERDICTS = ("answerable",)

    def __init__(self, path: str | Path | None = None, *, ttl_seconds: int = 604800):
        self.path = Path(path) if path else Path("data/memory/verified.json")
        self.ttl = int(ttl_seconds)
        self.entries: dict[str, MemoryEntry] = {}
        self.version = MEMORY_VERSION
        self._load()

    @staticmethod
    def make_key(query: str, intent: str) -> str:
        raw = f"{intent}::{' '.join((query or '').split())}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        for row in data.get("entries", []):
            e = MemoryEntry(
                key=row["key"], query=row.get("query", ""),
                verdict=row.get("verdict", ""), confidence=row.get("confidence", 0.0),
                payload=row.get("payload", {}), versions=row.get("versions", {}),
                stored_at=row.get("stored_at", time.time()), hits=row.get("hits", 0),
            )
            self.entries[e.key] = e

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "schema_version": self.version,
            "entries": [
                {"key": e.key, "query": e.query, "verdict": e.verdict,
                 "confidence": e.confidence, "payload": e.payload,
                 "versions": e.versions, "stored_at": e.stored_at, "hits": e.hits}
                for e in self.entries.values()
            ],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    # -----------------------------------------------------------------
    def remember(
        self, query: str, intent: str, verdict: str, confidence: float,
        payload: dict, versions: dict[str, str],
    ) -> bool:
        """
        يخزّن النتيجة إن كانت مؤكَّدة. يرجّع هل خُزّنت.

        الرفض هنا مقصود: الذاكرة ليست كاشاً.
        """
        if verdict not in self.ACCEPTED_VERDICTS:
            return False
        if confidence < self.MIN_CONFIDENCE:
            return False
        key = self.make_key(query, intent)
        self.entries[key] = MemoryEntry(
            key, query, verdict, confidence, payload, dict(versions)
        )
        return True

    def recall(
        self, query: str, intent: str, versions: dict[str, str]
    ) -> MemoryEntry | None:
        entry = self.entries.get(self.make_key(query, intent))
        if entry is None:
            return None
        if time.time() - entry.stored_at > self.ttl:
            del self.entries[entry.key]
            return None
        if not entry.is_valid(versions):
            del self.entries[entry.key]
            return None
        entry.hits += 1
        return entry

    def invalidate_all(self, reason: str = "") -> int:
        """يُستدعى بعد أي تعديل بشري (القسم 9: Event-Driven Updates)."""
        n = len(self.entries)
        self.entries.clear()
        return n

    def stats(self) -> dict:
        return {
            "entries": len(self.entries),
            "total_hits": sum(e.hits for e in self.entries.values()),
        }


__all__ = ["MEMORY_VERSION", "MemoryEngine", "MemoryEntry"]
