from __future__ import annotations

import json
import os
import pickle
import sqlite3
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None

from sklearn import __version__ as sklearn_version
from sklearn.exceptions import InconsistentVersionWarning
try:
    from torch import __version__ as torch_version
except ImportError:  # pragma: no cover - optional dependency
    torch_version = None
try:
    from transformers import __version__ as transformers_version
except ImportError:  # pragma: no cover - optional dependency
    transformers_version = None

from truthlens_feature_extractors import (
    history_encoder_resolution_payload,
    resolve_vision_encoder,
    resolve_history_encoder,
    resolve_text_encoder,
    text_encoder_resolution_payload,
    vision_encoder_resolution_payload,
)
from truthlens_data_pipeline.paths import resolve_runtime_path, runtime_storage_root

VISION_FEATURE_VERSION = "vision-v2"
VISION_FEATURE_COUNT = 12
HEAD_SPEC_VERSION = "2026-04-02"
ARCHITECTURE_PLAN_VERSION = "2026-04-02"
EVENT_STORE_LOCAL = "local"
EVENT_STORE_POSTGRES = "postgres"


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[4]


def _runtime_root() -> Path:
    return runtime_storage_root()


def _source_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _feedback_log_path() -> Path:
    return resolve_runtime_path("artifacts/reports/feedback_events.jsonl")


def _score_log_path() -> Path:
    return resolve_runtime_path("artifacts/reports/score_events.jsonl")


def _observation_log_path() -> Path:
    return resolve_runtime_path("artifacts/reports/browser_observations.jsonl")


def _feedback_db_path() -> Path:
    return resolve_runtime_path("artifacts/reports/feedback_events.sqlite3")


def _runtime_event_store_mode() -> str:
    raw_value = os.getenv("TRUTHLENS_RUNTIME_EVENT_STORE", EVENT_STORE_LOCAL).strip().lower()
    if raw_value in {EVENT_STORE_LOCAL, EVENT_STORE_POSTGRES}:
        return raw_value
    return EVENT_STORE_LOCAL


def runtime_event_store_backend() -> str:
    return _runtime_event_store_mode()


def _local_event_fallback_enabled() -> bool:
    raw_value = os.getenv("TRUTHLENS_LOCAL_EVENT_FALLBACK_ENABLED", "true").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _postgres_dsn() -> str | None:
    raw_value = os.getenv("TRUTHLENS_DATABASE_URL", "").strip()
    if not raw_value:
        return None
    if raw_value.startswith("postgresql+psycopg://"):
        return "postgresql://" + raw_value.removeprefix("postgresql+psycopg://")
    return raw_value


def _postgres_available() -> bool:
    return _runtime_event_store_mode() == EVENT_STORE_POSTGRES and _postgres_dsn() is not None and psycopg is not None


def _should_write_local_fallback() -> bool:
    return _runtime_event_store_mode() == EVENT_STORE_LOCAL or _local_event_fallback_enabled()


def model_dir() -> Path:
    path = _runtime_root() / "artifacts" / "trained_models" / "latest"
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
    if transformers_version is not None:
        payload["transformers"] = str(transformers_version)
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
    vision_encoder_override: str | None = None,
    history_encoder_override: str | None = None,
) -> list[dict[str, Any]]:
    text_encoder = text_encoder_override or "count-vectorizer-bigrams"
    vision_encoder = vision_encoder_override or VISION_FEATURE_VERSION
    history_encoder = history_encoder_override or "sequence-summary-v1"
    text_artifact_keys = ["text_model"]
    if text_encoder == "count-vectorizer-bigrams":
        text_artifact_keys = ["text_vectorizer", "text_model"]
    vision_backend = "sklearn-logistic-regression"
    vision_artifact_keys = ["vision_model"]
    vision_supports_attribution = True
    vision_supports_counterfactuals = True
    if vision_encoder == "tiny-cnn-thumbnail":
        vision_backend = "torch-cnn"
        vision_artifact_keys = ["vision_encoder_artifacts", "vision_model"]
        vision_supports_attribution = False
        vision_supports_counterfactuals = False
    elif vision_encoder == "vision-transformer":
        vision_backend = "torch-transformers"
        vision_artifact_keys = ["vision_encoder_artifacts", "vision_model"]
        vision_supports_attribution = False
        vision_supports_counterfactuals = False
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
            "backend": vision_backend,
            "encoder": vision_encoder,
            "artifact_keys": vision_artifact_keys,
            "feature_count": VISION_FEATURE_COUNT,
            "supports_attribution": vision_supports_attribution,
            "supports_counterfactuals": vision_supports_counterfactuals,
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
        vision_encoder_override=str(
            model_info.get("vision_encoder_resolution", {}).get("actual_encoder", VISION_FEATURE_VERSION)
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
        vision_resolution = vision_encoder_resolution_payload(resolve_vision_encoder())
        history_resolution = history_encoder_resolution_payload(resolve_history_encoder())
        return {
            "mode": "bootstrap",
            "model_version": "bootstrap-v0",
            "trained_at": None,
            "artifact_status": "missing",
            "head_specs": runtime_head_specs(
                text_encoder_override=str(text_resolution.get("actual_encoder", "count-vectorizer-bigrams")),
                vision_encoder_override=str(vision_resolution.get("actual_encoder", VISION_FEATURE_VERSION)),
                history_encoder_override=str(history_resolution.get("actual_encoder", "sequence-summary-v1")),
            ),
            "head_spec_version": HEAD_SPEC_VERSION,
            "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
            "architecture_layers": runtime_architecture_layers(),
            "text_encoder_resolution": text_resolution,
            "vision_encoder_resolution": vision_resolution,
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
    vision_encoder_payload = payload.get("vision_encoder_resolution")
    if not isinstance(vision_encoder_payload, dict):
        vision_encoder_payload = {
            "requested_encoder": "vision-v2",
            "actual_encoder": "vision-v2",
            "fallback_used": False,
            "image_size": 32,
            "conv_channels": [8, 16],
            "hidden_dim": 32,
            "patch_size": 8,
            "transformer_hidden_size": 64,
            "transformer_num_hidden_layers": 2,
            "transformer_num_attention_heads": 4,
            "transformer_intermediate_size": 128,
            "transformer_pooling": "cls",
            "epochs": 0,
            "learning_rate": 0.0,
            "fallback_reason": "trained artifact predates explicit vision encoder metadata",
        }
    history_encoder_payload = payload.get("history_encoder_resolution")
    if not isinstance(history_encoder_payload, dict):
        history_encoder_payload = history_encoder_resolution_payload(resolve_history_encoder())
    payload["text_encoder_resolution"] = encoder_payload
    payload["vision_encoder_resolution"] = vision_encoder_payload
    payload["history_encoder_resolution"] = history_encoder_payload
    payload["head_specs"] = runtime_head_specs(
        text_encoder_override=str(encoder_payload.get("actual_encoder", "count-vectorizer-bigrams")),
        vision_encoder_override=str(vision_encoder_payload.get("actual_encoder", VISION_FEATURE_VERSION)),
        history_encoder_override=str(history_encoder_payload.get("actual_encoder", "sequence-summary-v1")),
    )
    payload["head_spec_version"] = HEAD_SPEC_VERSION
    payload["architecture_plan_version"] = ARCHITECTURE_PLAN_VERSION
    payload["architecture_layers"] = runtime_architecture_layers()
    payload["runtime_library_versions"] = runtime_library_versions()
    payload["runtime_model_contracts"] = runtime_model_contracts()
    return payload


def load_feedback_events() -> list[dict[str, Any]]:
    if _postgres_available():
        return _load_feedback_events_postgres()
    db_path = _feedback_db_path()
    if db_path.exists():
        with sqlite3.connect(db_path) as connection:
            _ensure_feedback_table(connection)
            cursor = connection.execute(
                """
                SELECT
                    feedback_id,
                    item_id,
                    item_hash,
                    observation_id,
                    channel_name,
                    model_version,
                    policy_version,
                    action_shown,
                    user_action,
                    explanation_id,
                    before_score,
                    after_score,
                    timestamp,
                    runtime_context_json,
                    artifact_provenance_json,
                    manual_report_json
                FROM feedback_events
                ORDER BY rowid ASC
                """
            )
            db_rows = [
                {
                    "feedback_id": feedback_id,
                    "item_id": item_id,
                    "item_hash": item_hash,
                    "observation_id": observation_id,
                    "channel_name": channel_name,
                    "model_version": model_version,
                    "policy_version": policy_version,
                    "action_shown": action_shown,
                    "user_action": user_action,
                    "explanation_id": explanation_id,
                    "before_score": before_score,
                    "after_score": after_score,
                    "timestamp": timestamp,
                    "runtime_context": json.loads(runtime_context_json)
                    if runtime_context_json
                    else None,
                    "artifact_provenance": json.loads(artifact_provenance_json)
                    if artifact_provenance_json
                    else None,
                    "manual_report": json.loads(manual_report_json)
                    if manual_report_json
                    else None,
                }
                for (
                    feedback_id,
                    item_id,
                    item_hash,
                    observation_id,
                    channel_name,
                    model_version,
                    policy_version,
                    action_shown,
                    user_action,
                    explanation_id,
                    before_score,
                    after_score,
                    timestamp,
                    runtime_context_json,
                    artifact_provenance_json,
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
    if _postgres_available():
        return _load_score_events_postgres()
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


def load_browser_observations() -> list[dict[str, Any]]:
    if _postgres_available():
        return _load_browser_observations_postgres()
    db_path = _feedback_db_path()
    if db_path.exists():
        with sqlite3.connect(db_path) as connection:
            _ensure_browser_observation_table(connection)
            cursor = connection.execute(
                """
                SELECT
                    observation_id,
                    item_id,
                    item_hash,
                    title_snapshot,
                    channel_name,
                    channel_url,
                    link_url,
                    thumbnail_ref,
                    description_snapshot,
                    transcript_excerpt,
                    metadata_json,
                    runtime_context_json,
                    distilled_features_json,
                    score_snapshot_json,
                    provenance_json
                FROM browser_observations
                ORDER BY rowid ASC
                """
            )
            return [
                {
                    "observation_id": observation_id,
                    "item_id": item_id,
                    "item_hash": item_hash,
                    "title_snapshot": title_snapshot,
                    "channel_name": channel_name,
                    "channel_url": channel_url,
                    "link_url": link_url,
                    "thumbnail_ref": thumbnail_ref,
                    "description_snapshot": description_snapshot,
                    "transcript_excerpt": transcript_excerpt,
                    "metadata": json.loads(metadata_json) if metadata_json else {},
                    "runtime_context": json.loads(runtime_context_json) if runtime_context_json else {},
                    "distilled_features": json.loads(distilled_features_json)
                    if distilled_features_json
                    else {},
                    "score_snapshot": json.loads(score_snapshot_json) if score_snapshot_json else {},
                    "provenance": json.loads(provenance_json) if provenance_json else {},
                }
                for (
                    observation_id,
                    item_id,
                    item_hash,
                    title_snapshot,
                    channel_name,
                    channel_url,
                    link_url,
                    thumbnail_ref,
                    description_snapshot,
                    transcript_excerpt,
                    metadata_json,
                    runtime_context_json,
                    distilled_features_json,
                    score_snapshot_json,
                    provenance_json,
                ) in cursor.fetchall()
            ]
    path = _observation_log_path()
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
            feedback_id TEXT,
            item_id TEXT NOT NULL,
            item_hash TEXT,
            observation_id TEXT,
            channel_name TEXT,
            model_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            action_shown TEXT NOT NULL,
            user_action TEXT NOT NULL,
            explanation_id TEXT,
            before_score REAL,
            after_score REAL,
            timestamp TEXT NOT NULL,
            runtime_context_json TEXT,
            artifact_provenance_json TEXT,
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
    if "feedback_id" not in columns:
        connection.execute("ALTER TABLE feedback_events ADD COLUMN feedback_id TEXT")
    if "observation_id" not in columns:
        connection.execute("ALTER TABLE feedback_events ADD COLUMN observation_id TEXT")
    if "runtime_context_json" not in columns:
        connection.execute("ALTER TABLE feedback_events ADD COLUMN runtime_context_json TEXT")
    if "artifact_provenance_json" not in columns:
        connection.execute("ALTER TABLE feedback_events ADD COLUMN artifact_provenance_json TEXT")
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


def _ensure_browser_observation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS browser_observations (
            observation_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_hash TEXT,
            title_snapshot TEXT NOT NULL,
            channel_name TEXT,
            channel_url TEXT,
            link_url TEXT,
            thumbnail_ref TEXT,
            description_snapshot TEXT,
            transcript_excerpt TEXT,
            metadata_json TEXT,
            runtime_context_json TEXT,
            distilled_features_json TEXT,
            score_snapshot_json TEXT,
            provenance_json TEXT NOT NULL
        )
        """
    )
    connection.commit()


def _postgres_connect():
    dsn = _postgres_dsn()
    if psycopg is None or not dsn:
        raise RuntimeError("Postgres runtime event storage is not configured.")
    return psycopg.connect(dsn)


def _ensure_postgres_feedback_table(connection: Any) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_events (
            feedback_id TEXT,
            item_id TEXT NOT NULL,
            item_hash TEXT,
            observation_id TEXT,
            channel_name TEXT,
            model_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            action_shown TEXT NOT NULL,
            user_action TEXT NOT NULL,
            explanation_id TEXT,
            before_score DOUBLE PRECISION,
            after_score DOUBLE PRECISION,
            timestamp TEXT NOT NULL,
            runtime_context_json TEXT,
            artifact_provenance_json TEXT,
            manual_report_json TEXT
        )
        """
    )


def _ensure_postgres_score_table(connection: Any) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS score_events (
            item_id TEXT NOT NULL,
            channel_name TEXT,
            model_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            recommended_action TEXT NOT NULL,
            risk_score DOUBLE PRECISION NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            uncertainty DOUBLE PRECISION NOT NULL,
            explanation_id TEXT,
            timestamp TEXT NOT NULL
        )
        """
    )


def _ensure_postgres_browser_observation_table(connection: Any) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS browser_observations (
            observation_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_hash TEXT,
            title_snapshot TEXT NOT NULL,
            channel_name TEXT,
            channel_url TEXT,
            link_url TEXT,
            thumbnail_ref TEXT,
            description_snapshot TEXT,
            transcript_excerpt TEXT,
            metadata_json TEXT,
            runtime_context_json TEXT,
            distilled_features_json TEXT,
            score_snapshot_json TEXT,
            provenance_json TEXT NOT NULL
        )
        """
    )


def ensure_runtime_event_store() -> None:
    if not _postgres_available():
        return
    with _postgres_connect() as connection:
        _ensure_postgres_feedback_table(connection)
        _ensure_postgres_score_table(connection)
        _ensure_postgres_browser_observation_table(connection)
        connection.commit()


def _load_feedback_events_postgres() -> list[dict[str, Any]]:
    with _postgres_connect() as connection:
        _ensure_postgres_feedback_table(connection)
        cursor = connection.execute(
            """
            SELECT
                feedback_id,
                item_id,
                item_hash,
                observation_id,
                channel_name,
                model_version,
                policy_version,
                action_shown,
                user_action,
                explanation_id,
                before_score,
                after_score,
                timestamp,
                runtime_context_json,
                artifact_provenance_json,
                manual_report_json
            FROM feedback_events
            ORDER BY timestamp ASC, item_id ASC
            """
        )
        return [
            {
                "feedback_id": feedback_id,
                "item_id": item_id,
                "item_hash": item_hash,
                "observation_id": observation_id,
                "channel_name": channel_name,
                "model_version": model_version,
                "policy_version": policy_version,
                "action_shown": action_shown,
                "user_action": user_action,
                "explanation_id": explanation_id,
                "before_score": before_score,
                "after_score": after_score,
                "timestamp": timestamp,
                "runtime_context": json.loads(runtime_context_json) if runtime_context_json else None,
                "artifact_provenance": json.loads(artifact_provenance_json)
                if artifact_provenance_json
                else None,
                "manual_report": json.loads(manual_report_json) if manual_report_json else None,
            }
            for (
                feedback_id,
                item_id,
                item_hash,
                observation_id,
                channel_name,
                model_version,
                policy_version,
                action_shown,
                user_action,
                explanation_id,
                before_score,
                after_score,
                timestamp,
                runtime_context_json,
                artifact_provenance_json,
                manual_report_json,
            ) in cursor.fetchall()
        ]


def _load_score_events_postgres() -> list[dict[str, Any]]:
    with _postgres_connect() as connection:
        _ensure_postgres_score_table(connection)
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
            ORDER BY timestamp ASC, item_id ASC
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


def _load_browser_observations_postgres() -> list[dict[str, Any]]:
    with _postgres_connect() as connection:
        _ensure_postgres_browser_observation_table(connection)
        cursor = connection.execute(
            """
            SELECT
                observation_id,
                item_id,
                item_hash,
                title_snapshot,
                channel_name,
                channel_url,
                link_url,
                thumbnail_ref,
                description_snapshot,
                transcript_excerpt,
                metadata_json,
                runtime_context_json,
                distilled_features_json,
                score_snapshot_json,
                provenance_json
            FROM browser_observations
            ORDER BY observation_id ASC
            """
        )
        return [
            {
                "observation_id": observation_id,
                "item_id": item_id,
                "item_hash": item_hash,
                "title_snapshot": title_snapshot,
                "channel_name": channel_name,
                "channel_url": channel_url,
                "link_url": link_url,
                "thumbnail_ref": thumbnail_ref,
                "description_snapshot": description_snapshot,
                "transcript_excerpt": transcript_excerpt,
                "metadata": json.loads(metadata_json) if metadata_json else {},
                "runtime_context": json.loads(runtime_context_json) if runtime_context_json else {},
                "distilled_features": json.loads(distilled_features_json)
                if distilled_features_json
                else {},
                "score_snapshot": json.loads(score_snapshot_json) if score_snapshot_json else {},
                "provenance": json.loads(provenance_json) if provenance_json else {},
            }
            for (
                observation_id,
                item_id,
                item_hash,
                title_snapshot,
                channel_name,
                channel_url,
                link_url,
                thumbnail_ref,
                description_snapshot,
                transcript_excerpt,
                metadata_json,
                runtime_context_json,
                distilled_features_json,
                score_snapshot_json,
                provenance_json,
            ) in cursor.fetchall()
        ]

def append_feedback_event(payload: dict[str, Any]) -> Path:
    path = _feedback_log_path()
    if _should_write_local_fallback():
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
                    feedback_id,
                    item_id,
                    item_hash,
                    observation_id,
                    channel_name,
                    model_version,
                    policy_version,
                    action_shown,
                    user_action,
                    explanation_id,
                    before_score,
                    after_score,
                    timestamp,
                    runtime_context_json,
                    artifact_provenance_json,
                    manual_report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("feedback_id"),
                    payload.get("item_id"),
                    payload.get("item_hash"),
                    payload.get("observation_id"),
                    payload.get("channel_name"),
                    payload.get("model_version"),
                    payload.get("policy_version"),
                    payload.get("action_shown"),
                    payload.get("user_action"),
                    payload.get("explanation_id"),
                    payload.get("before_score"),
                    payload.get("after_score"),
                    payload.get("timestamp"),
                    json.dumps(payload.get("runtime_context"), ensure_ascii=True)
                    if payload.get("runtime_context") is not None
                    else None,
                    json.dumps(payload.get("artifact_provenance"), ensure_ascii=True)
                    if payload.get("artifact_provenance") is not None
                    else None,
                    json.dumps(payload.get("manual_report"), ensure_ascii=True)
                    if payload.get("manual_report") is not None
                    else None,
                ),
            )
            connection.commit()
    if _postgres_available():
        with _postgres_connect() as connection:
            _ensure_postgres_feedback_table(connection)
            connection.execute(
                """
                INSERT INTO feedback_events (
                    feedback_id,
                    item_id,
                    item_hash,
                    observation_id,
                    channel_name,
                    model_version,
                    policy_version,
                    action_shown,
                    user_action,
                    explanation_id,
                    before_score,
                    after_score,
                    timestamp,
                    runtime_context_json,
                    artifact_provenance_json,
                    manual_report_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.get("feedback_id"),
                    payload.get("item_id"),
                    payload.get("item_hash"),
                    payload.get("observation_id"),
                    payload.get("channel_name"),
                    payload.get("model_version"),
                    payload.get("policy_version"),
                    payload.get("action_shown"),
                    payload.get("user_action"),
                    payload.get("explanation_id"),
                    payload.get("before_score"),
                    payload.get("after_score"),
                    payload.get("timestamp"),
                    json.dumps(payload.get("runtime_context"), ensure_ascii=True)
                    if payload.get("runtime_context") is not None
                    else None,
                    json.dumps(payload.get("artifact_provenance"), ensure_ascii=True)
                    if payload.get("artifact_provenance") is not None
                    else None,
                    json.dumps(payload.get("manual_report"), ensure_ascii=True)
                    if payload.get("manual_report") is not None
                    else None,
                ),
            )
            connection.commit()
    return path


def append_browser_observation(payload: dict[str, Any]) -> Path:
    path = _observation_log_path()
    if _should_write_local_fallback():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")
        db_path = _feedback_db_path()
        with sqlite3.connect(db_path) as connection:
            _ensure_browser_observation_table(connection)
            connection.execute(
                """
                INSERT INTO browser_observations (
                    observation_id,
                    item_id,
                    item_hash,
                    title_snapshot,
                    channel_name,
                    channel_url,
                    link_url,
                    thumbnail_ref,
                    description_snapshot,
                    transcript_excerpt,
                    metadata_json,
                    runtime_context_json,
                    distilled_features_json,
                    score_snapshot_json,
                    provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("observation_id"),
                    payload.get("item_id"),
                    payload.get("item_hash"),
                    payload.get("title_snapshot"),
                    payload.get("channel_name"),
                    payload.get("channel_url"),
                    payload.get("link_url"),
                    payload.get("thumbnail_ref"),
                    payload.get("description_snapshot"),
                    payload.get("transcript_excerpt"),
                    json.dumps(payload.get("metadata", {}), ensure_ascii=True),
                    json.dumps(payload.get("runtime_context", {}), ensure_ascii=True),
                    json.dumps(payload.get("distilled_features", {}), ensure_ascii=True),
                    json.dumps(payload.get("score_snapshot", {}), ensure_ascii=True),
                    json.dumps(payload.get("provenance", {}), ensure_ascii=True),
                ),
            )
            connection.commit()
    if _postgres_available():
        with _postgres_connect() as connection:
            _ensure_postgres_browser_observation_table(connection)
            connection.execute(
                """
                INSERT INTO browser_observations (
                    observation_id,
                    item_id,
                    item_hash,
                    title_snapshot,
                    channel_name,
                    channel_url,
                    link_url,
                    thumbnail_ref,
                    description_snapshot,
                    transcript_excerpt,
                    metadata_json,
                    runtime_context_json,
                    distilled_features_json,
                    score_snapshot_json,
                    provenance_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.get("observation_id"),
                    payload.get("item_id"),
                    payload.get("item_hash"),
                    payload.get("title_snapshot"),
                    payload.get("channel_name"),
                    payload.get("channel_url"),
                    payload.get("link_url"),
                    payload.get("thumbnail_ref"),
                    payload.get("description_snapshot"),
                    payload.get("transcript_excerpt"),
                    json.dumps(payload.get("metadata", {}), ensure_ascii=True),
                    json.dumps(payload.get("runtime_context", {}), ensure_ascii=True),
                    json.dumps(payload.get("distilled_features", {}), ensure_ascii=True),
                    json.dumps(payload.get("score_snapshot", {}), ensure_ascii=True),
                    json.dumps(payload.get("provenance", {}), ensure_ascii=True),
                ),
            )
            connection.commit()
    return path


def append_score_event(payload: dict[str, Any]) -> Path:
    path = _score_log_path()
    if _should_write_local_fallback():
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
    if _postgres_available():
        with _postgres_connect() as connection:
            _ensure_postgres_score_table(connection)
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
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def summarize_browser_observations(
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = observations if observations is not None else load_browser_observations()
    surface_counts = Counter(
        str(row.get("runtime_context", {}).get("surface", "unknown"))
        for row in rows
        if isinstance(row, dict)
    )
    action_counts = Counter(
        str(row.get("score_snapshot", {}).get("recommended_action", "none"))
        for row in rows
        if isinstance(row, dict)
    )
    unique_items = {
        str(row.get("item_id", "")).strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("item_id", "")).strip()
    }
    with_feedback_link = sum(
        1
        for row in rows
        if isinstance(row, dict) and str(row.get("score_snapshot", {}).get("explanation_id", "")).strip()
    )
    return {
        "total_observations": len(rows),
        "unique_items": len(unique_items),
        "surface_counts": dict(sorted(surface_counts.items())),
        "recommended_action_counts": dict(sorted(action_counts.items())),
        "with_score_link": with_feedback_link,
    }
