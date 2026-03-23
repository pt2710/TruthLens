from __future__ import annotations

SENSATIONAL_TOKENS = {
    "breaking",
    "shocking",
    "confirmed",
    "aliens",
    "secret",
    "urgent",
    "exposed",
    "what they do not want",
}


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def uppercase_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    uppercase = sum(1 for char in letters if char.isupper())
    return round(uppercase / len(letters), 4)


def count_sensational_tokens(value: str) -> int:
    lowered = value.lower()
    return sum(1 for token in SENSATIONAL_TOKENS if token in lowered)


def _tokenize(value: str) -> set[str]:
    tokens = {
        token.strip(".,!?;:\"'()[]{}").lower()
        for token in value.split()
        if len(token.strip(".,!?;:\"'()[]{}")) >= 4
    }
    return {token for token in tokens if token}


def transcript_overlap(title: str, transcript: str) -> float:
    title_tokens = _tokenize(title)
    transcript_tokens = _tokenize(transcript)
    if not title_tokens or not transcript_tokens:
        return 0.0
    overlap = len(title_tokens & transcript_tokens) / len(title_tokens)
    return round(overlap, 4)


def transcript_mismatch_score(title: str, transcript: str, token_hits: int | float) -> float:
    if not transcript.strip():
        return 0.0
    overlap = transcript_overlap(title, transcript)
    mismatch = min(1.0, max(0.0, (1.0 - overlap) * 0.72 + float(token_hits) * 0.08))
    return round(mismatch, 4)
