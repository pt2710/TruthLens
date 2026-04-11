from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BANNED_TRACKED_PATTERNS = (
    ".env",
    ".env.local",
    "artifacts/reports/youtube_oauth_token.json",
    ".venv/",
    "node_modules/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    "datasets/raw/",
    "datasets/interim/",
    "datasets/processed/",
    "datasets/labels/",
    "artifacts/trained_models/latest/model_bundle.pkl",
    "artifacts/eval_runs/",
    "artifacts/drift_reports/",
)
BANNED_HISTORY_PATHS = (
    ".env",
    ".env.local",
    "artifacts/reports/youtube_oauth_token.json",
)
SUSPICIOUS_KEY = re.compile(r"(?i)\b(api[_-]?key|client[_-]?secret|refresh[_-]?token|access[_-]?token)\b")
QUOTED_SECRET_VALUE = re.compile(r"^[\"']([A-Za-z0-9_\-]{20,})[\"']$")
UNQUOTED_SECRET_VALUE = re.compile(r"^[A-Za-z0-9_\-]{20,}$")
TEXT_SUFFIXES = {
    ".env",
    ".example",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
}
ALLOWED_TEXT_SCAN_FILES = {
    ".env.example",
}


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _tracked_files() -> list[str]:
    return [line.strip() for line in _git("ls-files").splitlines() if line.strip()]


def _iter_text_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for relative_path in paths:
        path = REPO_ROOT / relative_path
        if path.suffix.lower() in TEXT_SUFFIXES and path.is_file():
            files.append(path)
    return files


def _matches_banned_pattern(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized == ".env.example" or normalized.endswith("/.gitkeep"):
        return False
    for pattern in BANNED_TRACKED_PATTERNS:
        if pattern.endswith("/"):
            if normalized.startswith(pattern):
                return True
            continue
        if normalized == pattern:
            return True
    return False


def _looks_like_secret_literal(raw_value: str) -> bool:
    value = raw_value.strip().rstrip(",")
    if not value or any(marker in value for marker in ("${", "<", ">", "localhost", "127.0.0.1")):
        return False
    if "://" in value or "." in value or "/" in value:
        return False
    return bool(QUOTED_SECRET_VALUE.fullmatch(value) or UNQUOTED_SECRET_VALUE.fullmatch(value))


def _file_contains_suspicious_assignment(path: Path) -> bool:
    relative_path = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    if relative_path in ALLOWED_TEXT_SCAN_FILES:
        return False

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if not line or not SUSPICIOUS_KEY.search(line):
            continue
        parts = re.split(r"\s*[:=]\s*", line, maxsplit=1)
        if len(parts) != 2:
            continue
        left, right = parts
        if not SUSPICIOUS_KEY.search(left):
            continue
        if _looks_like_secret_literal(right):
            return True
    return False


def _history_contains_path(path: str) -> bool:
    output = _git("log", "--all", "--format=%H", "--", path)
    return bool(output.strip())


def main() -> int:
    tracked_files = _tracked_files()
    failures: list[str] = []

    banned_tracked = [path for path in tracked_files if _matches_banned_pattern(path)]
    if banned_tracked:
        failures.append(
            "Tracked files violate curated-release rules:\n- " + "\n- ".join(sorted(banned_tracked))
        )

    history_hits = [path for path in BANNED_HISTORY_PATHS if _history_contains_path(path)]
    if history_hits:
        failures.append(
            "Banned sensitive paths exist in Git history:\n- " + "\n- ".join(sorted(history_hits))
        )

    suspicious_matches: list[str] = []
    for path in _iter_text_files(tracked_files):
        if _file_contains_suspicious_assignment(path):
            suspicious_matches.append(str(path.relative_to(REPO_ROOT)))
    if suspicious_matches:
        failures.append(
            "Suspicious credential-like assignments detected in tracked text files:\n- "
            + "\n- ".join(sorted(suspicious_matches))
        )

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1

    print("release hygiene audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
