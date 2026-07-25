from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_CLEAN_RE = re.compile(r"[^\w\u0600-\u06ff]+", flags=re.UNICODE)
_MULTI_DASH_RE = re.compile(r"-{2,}")


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").strip().lower()
    value = _CLEAN_RE.sub("-", value)
    value = _MULTI_DASH_RE.sub("-", value).strip("-")
    return value or "untitled"


def first_non_empty(*values: Any, default: str = "Untitled") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def split_names(value: Any) -> list[str]:
    text = coerce_str(value)
    if not text:
        return []
    parts = re.split(r"[،,;/|]+", text)
    return [part.strip() for part in parts if part.strip()]


def infer_language(*texts: Any) -> str:
    joined = " ".join(coerce_str(text) or "" for text in texts)
    if not joined:
        return "ar"

    arabic = len(re.findall(r"[\u0600-\u06FF]", joined))
    latin = len(re.findall(r"[A-Za-z]", joined))

    if arabic > latin:
        return "ar"
    if latin > arabic:
        return "en"
    return "und"


def path_stem(path: str | Path) -> str:
    return Path(path).stem
