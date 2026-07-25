from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\ufeff",
}

ARABIC_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670]")
MULTISPACE_RE = re.compile(r"\s+")
TOKENS_SPLIT_RE = re.compile(r"\s+")

TOKEN_STRIP_CHARS = " \t\r\n.,;:!?…،؛()[]{}<>«»\"'“”‘’ـ|/\\`~@#$%^&*_+=—-"

OCR_FIXES = {
    "االله": "الله",
    "االلة": "الله",
    "اللهُ": "الله",
}

def normalize_surface_text(text: str | None) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)

    for ch in ZERO_WIDTH:
        text = text.replace(ch, "")

    text = text.replace("\u0640", "")  # tatweel
    text = text.replace("\u2009", " ")
    text = text.replace("\u202f", " ")
    text = MULTISPACE_RE.sub(" ", text).strip()

    # Safe OCR cleanup for common Allah ligature expansions.
    for src, dst in OCR_FIXES.items():
        text = re.sub(rf"(?<!\S){re.escape(src)}(?!\S)", dst, text)

    return text

def search_form_text(text: str | None) -> str:
    text = normalize_surface_text(text)
    if not text:
        return ""
    text = ARABIC_DIACRITICS_RE.sub("", text)
    text = MULTISPACE_RE.sub(" ", text).strip()
    return text

def tokenize_text(text: str | None) -> list[str]:
    normalized = search_form_text(text)
    if not normalized:
        return []

    tokens: list[str] = []
    for raw in TOKENS_SPLIT_RE.split(normalized):
        token = raw.strip(TOKEN_STRIP_CHARS).strip()
        if token:
            tokens.append(token)
    return tokens

def canonicalize_phrase(text: str | None) -> str:
    return " ".join(tokenize_text(text))

def is_ocr_noise(text: str | None) -> bool:
    s = normalize_surface_text(text)
    if not s:
        return True
    noise = sum(1 for ch in s if ch in {"ـ", " "})
    return noise >= max(8, len(s) // 2)
