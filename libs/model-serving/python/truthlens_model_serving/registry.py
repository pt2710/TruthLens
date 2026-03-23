from __future__ import annotations

import json
import os
import pickle
from collections import Counter
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
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


def _normalize_action(event: dict[str, Any]) -> str:
    return str(event.get("user_action", "unknown")).strip().lower() or "unknown"


def _normalize_channel(event: dict[str, Any]) -> tuple[str, str] | None:
    channel_name = str(event.get("channel_name", "")).strip()
    if not channel_name:
        return None
    return channel_name.lower(), channel_name


def summarize_feedback_events(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = events if events is not None else load_feedback_events()
    action_counts = Counter(_normalize_action(row) for row in rows)
    correction_actions = action_counts["not-misleading"] + action_counts["undo-hide"]
    channel_profiles: dict[str, dict[str, Any]] = {}
    for row in rows:
        channel = _normalize_channel(row)
        if channel is None:
            continue
        channel_key, channel_name = channel
        profile = channel_profiles.setdefault(
            channel_key,
            {
                "channel_name": channel_name,
                "event_count": 0,
                "report_count": 0,
                "dismiss_count": 0,
                "mute_count": 0,
                "confirm_count": 0,
            },
        )
        profile["event_count"] += 1
        action = _normalize_action(row)
        if action in {"report", "confirm-report"}:
            profile["report_count"] += 1
        if action in {"not-misleading", "undo-hide"}:
            profile["dismiss_count"] += 1
        if action == "mute-channel-local":
            profile["mute_count"] += 1
        if action in {"report", "confirm-report", "hide-locally", "mute-channel-local"}:
            profile["confirm_count"] += 1

    for profile in channel_profiles.values():
        event_count = max(int(profile["event_count"]), 1)
        profile["bias"] = round(
            max(
                -0.12,
                min(
                    0.12,
                    (
                        profile["dismiss_count"] * 0.05
                        - profile["report_count"] * 0.06
                        - profile["mute_count"] * 0.08
                    )
                    / event_count,
                ),
            ),
            4,
        )

    top_channels = sorted(
        channel_profiles.values(),
        key=lambda profile: (abs(float(profile["bias"])), int(profile["event_count"])),
        reverse=True,
    )[:5]
    return {
        "total_events": len(rows),
        "action_counts": dict(sorted(action_counts.items())),
        "correction_rate": round(correction_actions / max(len(rows), 1), 4),
        "channel_profiles": channel_profiles,
        "top_channels": top_channels,
    }
