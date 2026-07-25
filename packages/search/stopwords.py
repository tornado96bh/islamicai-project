from __future__ import annotations

ARABIC_STOPWORDS = {
    "في", "من", "على", "عن", "إلى", "الى", "و", "يا", "هل", "ما", "ماذا", "متى", "كيف",
    "قال", "فقال", "ثم", "قد", "كان", "كانت", "يكون", "تكون", "هذا", "هذه", "ذلك", "تلك",
    "الذي", "التي", "الذين", "اللاتي", "اللواتي", "ال", "ب", "ك", "ل", "و", "ف", "ثم", "إن", "أن",
    "أو", "بل", "حتى", "إذا", "إذ", "عند", "مع", "كل", "أي", "أين", "أينما", "حيث", "ما",
}
GENERIC_QUERY_TERMS = {
    "قال", "في", "من", "على", "عن", "الله", "الله", "عبد", "عبدالله", "عبد الله",
    "السلام", "عليه", "عليها", "عليهم", "عليهما", "عليه السلام", "صلى", "النبي",
}

def is_stopword(token: str | None) -> bool:
    token = (token or "").strip()
    if not token:
        return True
    if token in ARABIC_STOPWORDS:
        return True
    if len(token) == 1 and token not in {"و", "ف", "ب", "ك", "ل"}:
        return True
    return False

def is_generic_token(token: str | None) -> bool:
    token = (token or "").strip()
    if not token:
        return True
    if token in GENERIC_QUERY_TERMS:
        return True
    return is_stopword(token)

def is_generic_query(tokens: list[str]) -> bool:
    meaningful = [t for t in tokens if not is_generic_token(t)]
    return len(meaningful) == 0

def filter_candidate_phrase(candidate: str, original_query: str | None = None) -> bool:
    candidate = (candidate or "").strip()
    if not candidate:
        return False
    parts = candidate.split()
    if len(parts) == 1 and is_generic_token(parts[0]):
        # keep the original query if it is short and important, but suppress generic expansions
        if original_query and candidate == original_query.strip():
            return True
        return False
    return True
