from __future__ import annotations

import json
import os
import pickle
import sqlite3
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

from sklearn import __version__ as sklearn_version
from sklearn.exceptions import InconsistentVersionWarning

VISION_FEATURE_VERSION = "vision-v2"
VISION_FEATURE_COUNT = 12


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[4]


def _feedback_log_path() -> Path:
    return _repo_root() / "artifacts" / "reports" / "feedback_events.jsonl"


def _score_log_path() -> Path:
    return _repo_root() / "artifacts" / "reports" / "score_events.jsonl"


def _feedback_db_path() -> Path:
    return _repo_root() / "artifacts" / "reports" / "feedback_events.sqlite3"


def model_dir() -> Path:
    path = _repo_root() / "artifacts" / "trained_models" / "latest"
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_library_versions() -> dict[str, str]:
    return {
        "scikit_learn": sklearn_version,
    }


def runtime_model_contracts() -> dict[str, str]:
    return {
        "vision_feature_version": VISION_FEATURE_VERSION,
        "vision_feature_count": str(VISION_FEATURE_COUNT),
    }


def _artifact_status(model_info: dict[str, Any]) -> str:
    training_versions = model_info.get("training_library_versions", {})
    trained_sklearn = str(training_versions.get("scikit_learn", "")).strip()
    if not trained_sklearn:
        return "incompatible"
    trained_vision_version = str(model_info.get("vision_feature_version", "")).strip()
    if trained_vision_version != runtime_model_contracts()["vision_feature_version"]:
        return "incompatible"
    trained_vision_feature_count = str(model_info.get("vision_feature_count", "")).strip()
    if trained_vision_feature_count != runtime_model_contracts()["vision_feature_count"]:
        return "incompatible"
    if trained_sklearn == runtime_library_versions()["scikit_learn"]:
        return "compatible"
    return "incompatible"


def load_model_bundle() -> dict[str, Any] | None:
    bundle_path = model_dir() / "model_bundle.pkl"
    if not bundle_path.exists():
        return None
    model_info = load_model_info()
    if model_info.get("artifact_status") != "compatible":
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InconsistentVersionWarning)
            with bundle_path.open("rb") as handle:
                return pickle.load(handle)
    except (OSError, pickle.PickleError, AttributeError, EOFError, ModuleNotFoundError, ValueError):
        return None


def load_model_info() -> dict[str, Any]:
    info_path = model_dir() / "model_info.json"
    if not info_path.exists():
        return {
            "mode": "bootstrap",
            "model_version": "bootstrap-v0",
            "trained_at": None,
            "artifact_status": "missing",
            "runtime_library_versions": runtime_library_versions(),
            "runtime_model_contracts": runtime_model_contracts(),
        }
    payload = json.loads(info_path.read_text(encoding="utf-8"))
    payload["artifact_status"] = _artifact_status(payload)
    payload["runtime_library_versions"] = runtime_library_versions()
    payload["runtime_model_contracts"] = runtime_model_contracts()
    return payload


def load_feedback_events() -> list[dict[str, Any]]:
    db_path = _feedback_db_path()
    if db_path.exists():
        with sqlite3.connect(db_path) as connection:
            _ensure_feedback_table(connection)
            cursor = connection.execute(
                """
                SELECT
                    item_id,
                    item_hash,
                    channel_name,
                    model_version,
                    policy_version,
                    action_shown,
                    user_action,
                    explanation_id,
                    before_score,
                    after_score,
                    timestamp
                FROM feedback_events
                ORDER BY rowid ASC
                """
            )
            db_rows = [
                {
                    "item_id": item_id,
                    "item_hash": item_hash,
                    "channel_name": channel_name,
                    "model_version": model_version,
                    "policy_version": policy_version,
                    "action_shown": action_shown,
                    "user_action": user_action,
                    "explanation_id": explanation_id,
                    "before_score": before_score,
                    "after_score": after_score,
                    "timestamp": timestamp,
                }
                for (
                    item_id,
                    item_hash,
                    channel_name,
                    model_version,
                    policy_version,
                    action_shown,
                    user_action,
                    explanation_id,
                    before_score,
                    after_score,
                    timestamp,
                ) in cursor.fetchall()
            ]
        return db_rows
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


def load_score_events() -> list[dict[str, Any]]:
    db_path = _feedback_db_path()
    if db_path.exists():
        with sqlite3.connect(db_path) as connection:
            _ensure_score_table(connection)
            cursor = connection.execute(
                """
                SELECT
                    item_id,
                    channel_name,
                    model_version,
                    policy_version,
                    recommended_action,
                    risk_score,
                    confidence,
                    uncertainty,
                    explanation_id,
                    timestamp
                FROM score_events
                ORDER BY rowid ASC
                """
            )
            return [
                {
                    "item_id": item_id,
                    "channel_name": channel_name,
                    "model_version": model_version,
                    "policy_version": policy_version,
                    "recommended_action": recommended_action,
                    "risk_score": risk_score,
                    "confidence": confidence,
                    "uncertainty": uncertainty,
                    "explanation_id": explanation_id,
                    "timestamp": timestamp,
                }
                for (
                    item_id,
                    channel_name,
                    model_version,
                    policy_version,
                    recommended_action,
                    risk_score,
                    confidence,
                    uncertainty,
                    explanation_id,
                    timestamp,
                ) in cursor.fetchall()
            ]
    path = _score_log_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _ensure_feedback_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_events (
            item_id TEXT NOT NULL,
            item_hash TEXT,
            channel_name TEXT,
            model_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            action_shown TEXT NOT NULL,
            user_action TEXT NOT NULL,
            explanation_id TEXT,
            before_score REAL,
            after_score REAL,
            timestamp TEXT NOT NULL
        )
        """
    )
    connection.commit()


def _ensure_score_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS score_events (
            item_id TEXT NOT NULL,
            channel_name TEXT,
            model_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            recommended_action TEXT NOT NULL,
            risk_score REAL NOT NULL,
            confidence REAL NOT NULL,
            uncertainty REAL NOT NULL,
            explanation_id TEXT,
            timestamp TEXT NOT NULL
        )
        """
    )
    connection.commit()


def append_feedback_event(payload: dict[str, Any]) -> Path:
    path = _feedback_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")
    db_path = _feedback_db_path()
    with sqlite3.connect(db_path) as connection:
        _ensure_feedback_table(connection)
        connection.execute(
            """
            INSERT INTO feedback_events (
                item_id,
                item_hash,
                channel_name,
                model_version,
                policy_version,
                action_shown,
                user_action,
                explanation_id,
                before_score,
                after_score,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("item_id"),
                payload.get("item_hash"),
                payload.get("channel_name"),
                payload.get("model_version"),
                payload.get("policy_version"),
                payload.get("action_shown"),
                payload.get("user_action"),
                payload.get("explanation_id"),
                payload.get("before_score"),
                payload.get("after_score"),
                payload.get("timestamp"),
            ),
        )
        connection.commit()
    return path


def append_score_event(payload: dict[str, Any]) -> Path:
    path = _score_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")
    db_path = _feedback_db_path()
    with sqlite3.connect(db_path) as connection:
        _ensure_score_table(connection)
        connection.execute(
            """
            INSERT INTO score_events (
                item_id,
                channel_name,
                model_version,
                policy_version,
                recommended_action,
                risk_score,
                confidence,
                uncertainty,
                explanation_id,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("item_id"),
                payload.get("channel_name"),
                payload.get("model_version"),
                payload.get("policy_version"),
                payload.get("recommended_action"),
                payload.get("risk_score"),
                payload.get("confidence"),
                payload.get("uncertainty"),
                payload.get("explanation_id"),
                payload.get("timestamp"),
            ),
        )
        connection.commit()
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


def summarize_score_events(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = events if events is not None else load_score_events()
    action_counts = Counter(str(row.get("recommended_action", "none")) for row in rows)
    return {
        "total_events": len(rows),
        "action_counts": dict(sorted(action_counts.items())),
        "average_risk_score": round(
            sum(float(row.get("risk_score", 0.0)) for row in rows) / max(len(rows), 1),
            4,
        ),
        "average_uncertainty": round(
            sum(float(row.get("uncertainty", 0.0)) for row in rows) / max(len(rows), 1),
            4,
        ),
    }
