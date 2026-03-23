from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _feedback_log_path() -> Path:
    return _repo_root() / "artifacts" / "reports" / "feedback_events.jsonl"


def model_dir() -> Path:
    path = _repo_root() / "artifacts" / "trained_models" / "latest"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_model_bundle() -> dict[str, Any] | None:
    bundle_path = model_dir() / "model_bundle.pkl"
    if not bundle_path.exists():
        return None
    with bundle_path.open("rb") as handle:
        return pickle.load(handle)


def load_model_info() -> dict[str, Any]:
    info_path = model_dir() / "model_info.json"
    if not info_path.exists():
        return {
            "mode": "bootstrap",
            "model_version": "bootstrap-v0",
            "trained_at": None,
        }
    return json.loads(info_path.read_text(encoding="utf-8"))


def load_feedback_events() -> list[dict[str, Any]]:
    path = _feedback_log_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_feedback_event(payload: dict[str, Any]) -> Path:
    path = _feedback_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")
    return path
