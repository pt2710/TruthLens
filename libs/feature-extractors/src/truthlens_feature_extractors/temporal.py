from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_ENCODER_CONFIG = {
    "requested_encoder": "lstm-sequence",
    "fallback_encoder": "sequence-summary-v1",
    "sequence_length": 4,
    "hidden_dim": 16,
    "num_layers": 1,
    "epochs": 60,
    "learning_rate": 0.01,
}


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[4]


def _source_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _history_encoder_config_path() -> Path:
    override_path = _repo_root() / "configs" / "models" / "history_encoder.json"
    if override_path.exists():
        return override_path
    return _source_repo_root() / "configs" / "models" / "history_encoder.json"


@dataclass(slots=True)
class HistoryEncoderResolution:
    requested_encoder: str
    actual_encoder: str
    fallback_used: bool
    sequence_length: int
    hidden_dim: int
    num_layers: int
    epochs: int
    learning_rate: float
    fallback_reason: str | None = None


def load_history_encoder_config() -> dict[str, Any]:
    path = _history_encoder_config_path()
    if not path.exists():
        return DEFAULT_HISTORY_ENCODER_CONFIG.copy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    merged = DEFAULT_HISTORY_ENCODER_CONFIG.copy()
    if isinstance(payload, dict):
        merged.update({key: value for key, value in payload.items() if value is not None})
    return merged


def temporal_torch_available() -> bool:
    return importlib.util.find_spec("torch") is not None


def resolve_history_encoder() -> HistoryEncoderResolution:
    config = load_history_encoder_config()
    requested_encoder = str(config.get("requested_encoder", "sequence-summary-v1")).strip()
    fallback_encoder = str(config.get("fallback_encoder", "sequence-summary-v1")).strip()
    sequence_length = int(config.get("sequence_length", 4))
    hidden_dim = int(config.get("hidden_dim", 16))
    num_layers = int(config.get("num_layers", 1))
    epochs = int(config.get("epochs", 60))
    learning_rate = float(config.get("learning_rate", 0.01))

    if requested_encoder == "lstm-sequence":
        if temporal_torch_available():
            return HistoryEncoderResolution(
                requested_encoder=requested_encoder,
                actual_encoder="lstm-sequence",
                fallback_used=False,
                sequence_length=sequence_length,
                hidden_dim=hidden_dim,
                num_layers=num_layers,
                epochs=epochs,
                learning_rate=learning_rate,
            )
        return HistoryEncoderResolution(
            requested_encoder=requested_encoder,
            actual_encoder=fallback_encoder,
            fallback_used=True,
            sequence_length=sequence_length,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            epochs=epochs,
            learning_rate=learning_rate,
            fallback_reason="torch is not installed in the active environment",
        )

    return HistoryEncoderResolution(
        requested_encoder=requested_encoder,
        actual_encoder=requested_encoder,
        fallback_used=False,
        sequence_length=sequence_length,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        epochs=epochs,
        learning_rate=learning_rate,
    )


def fallback_history_encoder_resolution(
    resolution: HistoryEncoderResolution,
    *,
    reason: str,
    fallback_encoder: str = "sequence-summary-v1",
) -> HistoryEncoderResolution:
    return HistoryEncoderResolution(
        requested_encoder=resolution.requested_encoder,
        actual_encoder=fallback_encoder,
        fallback_used=True,
        sequence_length=resolution.sequence_length,
        hidden_dim=resolution.hidden_dim,
        num_layers=resolution.num_layers,
        epochs=resolution.epochs,
        learning_rate=resolution.learning_rate,
        fallback_reason=reason,
    )


def history_encoder_resolution_payload(resolution: HistoryEncoderResolution) -> dict[str, Any]:
    return asdict(resolution)
