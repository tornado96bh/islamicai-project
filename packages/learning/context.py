from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import json

from .dictionary import search_form_text, tokenize_text


@dataclass(slots=True)
class ContextEntry:
    word: str
    frequency: int = 0
    left: dict[str, int] = field(default_factory=dict)
    right: dict[str, int] = field(default_factory=dict)


class ContextLearner:
    def __init__(self, storage_path: str | Path | None = None, window: int = 2):
        default_path = Path(__file__).resolve().parents[2] / "storage" / "learning" / "context.json"
        self.storage_path = Path(storage_path) if storage_path else default_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.window = window
        self.entries: dict[str, ContextEntry] = {}
        self._left: dict[str, Counter[str]] = defaultdict(Counter)
        self._right: dict[str, Counter[str]] = defaultdict(Counter)
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
                entry = ContextEntry(**item)
                self.entries[entry.word] = entry
                self._left[entry.word] = Counter(entry.left)
                self._right[entry.word] = Counter(entry.right)
            except Exception:
                continue

    def save(self) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": [
                {
                    "word": entry.word,
                    "frequency": entry.frequency,
                    "left": dict(self._left.get(entry.word, Counter(entry.left))),
                    "right": dict(self._right.get(entry.word, Counter(entry.right))),
                }
                for entry in self.entries.values()
            ],
        }
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def learn_text(self, text: str | None) -> int:
        return self.learn_tokens(tokenize_text(search_form_text(text)))

    def learn_tokens(self, tokens: Iterable[str]) -> int:
        items = [search_form_text(token) for token in tokens if search_form_text(token)]
        if not items:
            return 0

        learned = 0
        for i, word in enumerate(items):
            entry = self.entries.get(word)
            if entry is None:
                entry = ContextEntry(word=word)
            entry.frequency += 1
            self.entries[word] = entry

            start = max(0, i - self.window)
            end = min(len(items), i + self.window + 1)

            for left in items[start:i]:
                self._left[word][left] += 1
                learned += 1

            for right in items[i + 1 : end]:
                self._right[word][right] += 1
                learned += 1

        return learned

    def neighbors(self, word: str, limit: int = 10) -> list[dict]:
        key = search_form_text(word)
        if not key:
            return []

        left = self._left.get(key, Counter())
        right = self._right.get(key, Counter())

        combined = Counter()
        combined.update(left)
        combined.update(right)

        return [{"word": token, "score": score} for token, score in combined.most_common(limit)]

    def __len__(self) -> int:
        return len(self.entries)
