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
try:
    from torch import __version__ as torch_version
except ImportError:  # pragma: no cover - optional dependency
    torch_version = None

from truthlens_feature_extractors import (
    history_encoder_resolution_payload,
    resolve_history_encoder,
    resolve_text_encoder,
    text_encoder_resolution_payload,
)

VISION_FEATURE_VERSION = "vision-v2"
VISION_FEATURE_COUNT = 12
HEAD_SPEC_VERSION = "2026-04-02"
ARCHITECTURE_PLAN_VERSION = "2026-04-02"


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[4]


def _source_repo_root() -> Path:
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


def _architecture_layers_path() -> Path:
    override_path = _repo_root() / "configs" / "models" / "architecture_layers.json"
    if override_path.exists():
        return override_path
    return _source_repo_root() / "configs" / "models" / "architecture_layers.json"


def runtime_library_versions() -> dict[str, str]:
    payload = {
        "scikit_learn": sklearn_version,
    }
    if torch_version is not None:
        payload["torch"] = str(torch_version)
    return payload


def runtime_architecture_layers() -> list[dict[str, Any]]:
    path = _architecture_layers_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    components = payload.get("components", [])
    if not isinstance(components, list):
        return []
    return [component for component in components if isinstance(component, dict)]


def runtime_head_specs(
    *,
    text_encoder_override: str | None = None,
    history_encoder_override: str | None = None,
) -> list[dict[str, Any]]:
    text_encoder = text_encoder_override or "count-vectorizer-bigrams"
    history_encoder = history_encoder_override or "sequence-summary-v1"
    text_artifact_keys = ["text_model"]
    if text_encoder == "count-vectorizer-bigrams":
        text_artifact_keys = ["text_vectorizer", "text_model"]
    history_backend = "sklearn-logistic-regression"
    history_artifact_keys = ["history_model"]
    history_supports_attribution = True
    history_supports_counterfactuals = True
    if history_encoder == "lstm-sequence":
        history_backend = "torch-lstm"
        history_artifact_keys = ["history_sequence_artifacts", "history_model"]
        history_supports_attribution = False
        history_supports_counterfactuals = False
    return [
        {
            "name": "text",
            "family": "title-encoder",
            "backend": "sklearn-logistic-regression",
            "encoder": text_encoder,
            "artifact_keys": text_artifact_keys,
            "supports_attribution": True,
            "supports_counterfactuals": True,
            "supports_sequence": False,
        },
        {
            "name": "vision",
            "family": "thumbnail-feature-head",
            "backend": "sklearn-logistic-regression",
            "encoder": VISION_FEATURE_VERSION,
            "artifact_keys": ["vision_model"],
            "feature_count": VISION_FEATURE_COUNT,
            "supports_attribution": True,
            "supports_counterfactuals": True,
            "supports_sequence": False,
        },
        {
            "name": "metadata",
            "family": "tabular-risk-head",
            "backend": "sklearn-logistic-regression",
            "encoder": "handcrafted-metadata-v1",
            "artifact_keys": ["metadata_model"],
            "supports_attribution": True,
            "supports_counterfactuals": True,
            "supports_sequence": False,
        },
        {
            "name": "history",
            "family": "temporal-channel-head",
            "backend": history_backend,
            "encoder": history_encoder,
            "artifact_keys": history_artifact_keys,
            "supports_attribution": history_supports_attribution,
            "supports_counterfactuals": history_supports_counterfactuals,
            "supports_sequence": True,
        },
        {
            "name": "anomaly",
            "family": "packaging-vae-anomaly-head",
            "backend": "torch-vae",
            "encoder": "vision-metadata-vae-v1",
            "artifact_keys": ["packaging_vae_artifacts"],
            "supports_attribution": True,
            "supports_counterfactuals": False,
            "supports_sequence": False,
        },
        {
            "name": "fusion",
            "family": "multimodal-fusion-head",
            "backend": "sklearn-logistic-regression",
            "encoder": "score-stack-v1",
            "artifact_keys": ["fusion_model"],
            "supports_attribution": True,
            "supports_counterfactuals": True,
            "supports_sequence": False,
        },
        {
            "name": "calibration",
            "family": "probability-calibration-head",
            "backend": "sklearn-logistic-regression",
            "encoder": "platt-scaling-v1",
            "artifact_keys": ["calibration_model"],
            "supports_attribution": False,
            "supports_counterfactuals": False,
            "supports_sequence": False,
        },
    ]


def runtime_model_contracts() -> dict[str, str]:
    return {
        "vision_feature_version": VISION_FEATURE_VERSION,
        "vision_feature_count": str(VISION_FEATURE_COUNT),
        "head_spec_version": HEAD_SPEC_VERSION,
        "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
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
    trained_head_spec_version = str(model_info.get("head_spec_version", "")).strip()
    if trained_head_spec_version != runtime_model_contracts()["head_spec_version"]:
        return "incompatible"
    trained_heads = model_info.get("head_specs", [])
    runtime_heads = runtime_head_specs(
        text_encoder_override=str(
            model_info.get("text_encoder_resolution", {}).get("actual_encoder", "count-vectorizer-bigrams")
        ),
        history_encoder_override=str(
            model_info.get("history_encoder_resolution", {}).get("actual_encoder", "sequence-summary-v1")
        ),
    )
    if not isinstance(trained_heads, list) or len(trained_heads) != len(runtime_heads):
        return "incompatible"
    trained_head_names = [str(head.get("name", "")) for head in trained_heads if isinstance(head, dict)]
    runtime_head_names = [str(head["name"]) for head in runtime_heads]
    if trained_head_names != runtime_head_names:
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
        text_resolution = text_encoder_resolution_payload(resolve_text_encoder())
        history_resolution = history_encoder_resolution_payload(resolve_history_encoder())
        return {
            "mode": "bootstrap",
            "model_version": "bootstrap-v0",
            "trained_at": None,
            "artifact_status": "missing",
            "head_specs": runtime_head_specs(
                text_encoder_override=str(text_resolution.get("actual_encoder", "count-vectorizer-bigrams")),
                history_encoder_override=str(history_resolution.get("actual_encoder", "sequence-summary-v1")),
            ),
            "head_spec_version": HEAD_SPEC_VERSION,
            "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
            "architecture_layers": runtime_architecture_layers(),
            "text_encoder_resolution": text_resolution,
            "history_encoder_resolution": history_resolution,
            "fusion_profile": {
                "head_weights": {
                    "text": 0.32,
                    "vision": 0.26,
                    "metadata": 0.20,
                    "history": 0.22,
                    "anomaly": 0.15,
                },
                "strategy": "bootstrap-weighted-average",
            },
            "runtime_library_versions": runtime_library_versions(),
            "runtime_model_contracts": runtime_model_contracts(),
        }
    payload = json.loads(info_path.read_text(encoding="utf-8"))
    payload["artifact_status"] = _artifact_status(payload)
    encoder_payload = payload.get("text_encoder_resolution")
    if not isinstance(encoder_payload, dict):
        encoder_payload = text_encoder_resolution_payload(resolve_text_encoder())
    history_encoder_payload = payload.get("history_encoder_resolution")
    if not isinstance(history_encoder_payload, dict):
        history_encoder_payload = history_encoder_resolution_payload(resolve_history_encoder())
    payload["text_encoder_resolution"] = encoder_payload
    payload["history_encoder_resolution"] = history_encoder_payload
    payload["head_specs"] = runtime_head_specs(
        text_encoder_override=str(encoder_payload.get("actual_encoder", "count-vectorizer-bigrams")),
        history_encoder_override=str(history_encoder_payload.get("actual_encoder", "sequence-summary-v1")),
    )
    payload["head_spec_version"] = HEAD_SPEC_VERSION
    payload["architecture_plan_version"] = ARCHITECTURE_PLAN_VERSION
    payload["architecture_layers"] = runtime_architecture_layers()
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
                    timestamp,
                    manual_report_json
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
                    "manual_report": json.loads(manual_report_json)
                    if manual_report_json
                    else None,
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
                    manual_report_json,
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
            timestamp TEXT NOT NULL,
            manual_report_json TEXT
        )
        """
    )
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(feedback_events)").fetchall()
    }
    if "manual_report_json" not in columns:
        connection.execute("ALTER TABLE feedback_events ADD COLUMN manual_report_json TEXT")
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
                timestamp,
                manual_report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(payload.get("manual_report"), ensure_ascii=True)
                if payload.get("manual_report") is not None
                else None,
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
    if not channel_name or channel_name.lower() == "unknown channel":
        return None
    return channel_name.lower(), channel_name


def summarize_feedback_events(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = events if events is not None else load_feedback_events()
    score_rows = load_score_events()
    action_counts = Counter(_normalize_action(row) for row in rows)
    correction_actions = action_counts["not-misleading"] + action_counts["undo-hide"]
    channel_profiles: dict[str, dict[str, Any]] = {}
    scored_items_by_channel: dict[str, set[str]] = {}
    for row in score_rows:
        channel = _normalize_channel(row)
        if channel is None:
            continue
        channel_key, channel_name = channel
        item_id = str(row.get("item_id", "")).strip()
        if not item_id:
            continue
        scored_items_by_channel.setdefault(channel_key, set()).add(item_id)
        channel_profiles.setdefault(
            channel_key,
            {
                "channel_name": channel_name,
                "event_count": 0,
                "report_count": 0,
                "dismiss_count": 0,
                "mute_count": 0,
                "confirm_count": 0,
                "transparent_count": 0,
                "moderate_request_count": 0,
                "remove_request_count": 0,
            },
        )
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
                "transparent_count": 0,
                "moderate_request_count": 0,
                "remove_request_count": 0,
            },
        )
        profile["event_count"] += 1
        action = _normalize_action(row)
        if action in {"report", "confirm-report"}:
            profile["report_count"] += 1
            manual_report = row.get("manual_report")
            requested_outcome = "moderate"
            if isinstance(manual_report, dict):
                requested_outcome = str(
                    manual_report.get("requested_outcome", "moderate")
                ).strip().lower() or "moderate"
            if requested_outcome == "remove":
                profile["remove_request_count"] += 1
            else:
                profile["moderate_request_count"] += 1
        if action in {"not-misleading", "undo-hide"}:
            profile["dismiss_count"] += 1
        if action == "confirm-transparent":
            profile["transparent_count"] += 1
        if action == "mute-channel-local":
            profile["mute_count"] += 1
        if action in {"report", "confirm-report", "hide-locally", "mute-channel-local"}:
            profile["confirm_count"] += 1

    for profile in channel_profiles.values():
        event_count = max(int(profile["event_count"]), 1)
        channel_key = str(profile["channel_name"]).strip().lower()
        scored_item_count = len(scored_items_by_channel.get(channel_key, set()))
        moderate_request_count = int(profile["moderate_request_count"])
        remove_request_count = int(profile["remove_request_count"])
        transparent_count = int(profile["transparent_count"])
        weighted_negative_signal = moderate_request_count + (remove_request_count * 1.35)
        positive_signal = transparent_count * 0.75
        total_signal = max(scored_item_count, 0) + 4.0
        trust_score = round(
            max(
                0.0,
                min(
                    10.0,
                    10.0
                    * (
                        1.0
                        - max(0.0, (weighted_negative_signal + 2.0) - positive_signal)
                        / total_signal
                    ),
                ),
            ),
            2,
        )
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
        profile["scored_item_count"] = scored_item_count
        profile["reported_item_count"] = moderate_request_count + remove_request_count
        profile["trust_score"] = trust_score

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
