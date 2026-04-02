from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import numpy as np

DEFAULT_TEXT_ENCODER_CONFIG = {
    "requested_encoder": "sentence-transformer",
    "fallback_encoder": "count-vectorizer-bigrams",
    "sentence_transformer_model": "sentence-transformers/all-MiniLM-L6-v2",
}


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[4]


def _source_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _text_encoder_config_path() -> Path:
    override_path = _repo_root() / "configs" / "models" / "text_encoder.json"
    if override_path.exists():
        return override_path
    return _source_repo_root() / "configs" / "models" / "text_encoder.json"


@dataclass(slots=True)
class TextEncoderResolution:
    requested_encoder: str
    actual_encoder: str
    fallback_used: bool
    sentence_transformer_model: str | None = None
    fallback_reason: str | None = None


def load_text_encoder_config() -> dict[str, Any]:
    path = _text_encoder_config_path()
    if not path.exists():
        return DEFAULT_TEXT_ENCODER_CONFIG.copy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    merged = DEFAULT_TEXT_ENCODER_CONFIG.copy()
    if isinstance(payload, dict):
        merged.update({key: value for key, value in payload.items() if value is not None})
    return merged


def sentence_transformers_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def resolve_text_encoder() -> TextEncoderResolution:
    config = load_text_encoder_config()
    requested_encoder = str(config.get("requested_encoder", "count-vectorizer-bigrams")).strip()
    fallback_encoder = str(config.get("fallback_encoder", "count-vectorizer-bigrams")).strip()
    sentence_transformer_model = str(
        config.get("sentence_transformer_model", DEFAULT_TEXT_ENCODER_CONFIG["sentence_transformer_model"])
    ).strip()

    if requested_encoder == "sentence-transformer":
        if sentence_transformers_available():
            return TextEncoderResolution(
                requested_encoder=requested_encoder,
                actual_encoder="sentence-transformer",
                fallback_used=False,
                sentence_transformer_model=sentence_transformer_model,
            )
        return TextEncoderResolution(
            requested_encoder=requested_encoder,
            actual_encoder=fallback_encoder,
            fallback_used=True,
            sentence_transformer_model=sentence_transformer_model,
            fallback_reason="sentence-transformers is not installed in the active environment",
        )

    return TextEncoderResolution(
        requested_encoder=requested_encoder,
        actual_encoder=requested_encoder,
        fallback_used=False,
        sentence_transformer_model=sentence_transformer_model if requested_encoder == "sentence-transformer" else None,
    )


def fallback_text_encoder_resolution(
    resolution: TextEncoderResolution,
    *,
    reason: str,
    fallback_encoder: str = "count-vectorizer-bigrams",
) -> TextEncoderResolution:
    return TextEncoderResolution(
        requested_encoder=resolution.requested_encoder,
        actual_encoder=fallback_encoder,
        fallback_used=True,
        sentence_transformer_model=resolution.sentence_transformer_model,
        fallback_reason=reason,
    )


def text_encoder_resolution_payload(resolution: TextEncoderResolution) -> dict[str, Any]:
    return asdict(resolution)


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_name: str) -> Any:
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    return SentenceTransformer(model_name)


def sentence_transformer_matrix(texts: Sequence[str], model_name: str) -> np.ndarray:
    model = _load_sentence_transformer(model_name)
    embeddings = model.encode(
        list(texts),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype=float)
