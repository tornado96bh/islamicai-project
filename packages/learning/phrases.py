from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import json
import math

from .dictionary import search_form_text, tokenize_text


@dataclass(slots=True)
class PhraseEntry:
    phrase: str
    n: int
    frequency: int = 0
    document_frequency: int = 0
    first_seen: str | None = None
    last_seen: str | None = None


class PhraseLearner:
    def __init__(self, storage_path: str | Path | None = None, min_n: int = 2, max_n: int = 5):
        default_path = Path(__file__).resolve().parents[2] / "storage" / "learning" / "phrases.json"
        self.storage_path = Path(storage_path) if storage_path else default_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.min_n = min_n
        self.max_n = max_n
        self.entries: dict[str, PhraseEntry] = {}
        self._loaded = False
        self.load()

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self.storage_path.exists() or self.storage_path.stat().st_size == 0:
            return

        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            return

        for item in payload.get("entries", []):
            try:
                entry = PhraseEntry(**item)
                self.entries[entry.phrase] = entry
            except Exception:
                continue

    def save(self) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": [asdict(entry) for entry in self.entries.values()],
        }
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def learn_text(self, text: str | None) -> int:
        return self.learn_tokens(tokenize_text(text))

    def learn_tokens(self, tokens: Iterable[str]) -> int:
        items = [search_form_text(token) for token in tokens if search_form_text(token)]
        if len(items) < self.min_n:
            return 0

        ts = datetime.now(timezone.utc).isoformat()
        seen: set[str] = set()
        learned = 0

        upper_n = min(self.max_n, len(items))
        for n in range(self.min_n, upper_n + 1):
            for i in range(0, len(items) - n + 1):
                phrase = " ".join(items[i : i + n]).strip()
                if not phrase:
                    continue

                entry = self.entries.get(phrase)
                if entry is None:
                    entry = PhraseEntry(phrase=phrase, n=n, first_seen=ts)
                entry.frequency += 1
                entry.last_seen = ts
                self.entries[phrase] = entry
                seen.add(phrase)
                learned += 1

        for phrase in seen:
            self.entries[phrase].document_frequency += 1

        return learned

    def suggest(self, query: str, limit: int = 10) -> list[dict]:
        q = search_form_text(query)
        if not q:
            return []

        matches: list[tuple[float, PhraseEntry]] = []
        for entry in self.entries.values():
            score = 1.0 if entry.phrase == q else 0.0
            if q in entry.phrase:
                score += 0.75
            score += math.log1p(entry.frequency) / 8.0
            score += math.log1p(entry.document_frequency) / 15.0
            if score >= 0.2:
                matches.append((score, entry))

        matches.sort(key=lambda item: (item[0], item[1].frequency, item[1].phrase), reverse=True)

        return [
            {
                "phrase": entry.phrase,
                "n": entry.n,
                "score": round(score, 4),
                "frequency": entry.frequency,
                "document_frequency": entry.document_frequency,
            }
            for score, entry in matches[:limit]
        ]

    def __len__(self) -> int:
        return len(self.entries)
