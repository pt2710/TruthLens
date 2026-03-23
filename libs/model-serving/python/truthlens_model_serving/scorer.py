from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from truthlens_model_serving.registry import load_model_bundle, load_model_info
from truthlens_shared_schemas.contracts import ScoreItemRequest

SUSPICIOUS_TOKENS = {
    "breaking",
    "shocking",
    "confirmed",
    "aliens",
    "secret",
    "urgent",
    "exposed",
    "what they do not want",
}


@dataclass(slots=True)
class ModelSignals:
    text_score: float
    vision_score: float
    metadata_score: float
    fusion_score: float
    calibrated_score: float
    confidence: float
    uncertainty: float
    model_version: str
    mode: str
    feature_summary: dict[str, float]


def _safe_probability(model: Any, matrix: Any) -> float:
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(matrix)
        return float(probabilities[0][1])
    prediction = model.predict(matrix)
    return float(prediction[0])


def _title_summary(payload: ScoreItemRequest) -> dict[str, float]:
    title = payload.title
    lowered = title.lower()
    token_hits = sum(1 for token in SUSPICIOUS_TOKENS if token in lowered)
    uppercase_letters = sum(1 for char in title if char.isalpha() and char.isupper())
    alpha_letters = max(sum(1 for char in title if char.isalpha()), 1)
    return {
        "token_hits": float(token_hits),
        "title_length": float(len(title)),
        "uppercase_ratio": round(uppercase_letters / alpha_letters, 4),
    }


def _vision_vector(payload: ScoreItemRequest, summary: dict[str, float]) -> list[float]:
    thumbnail_signal: dict[str, float] = {}
    if payload.thumbnail_ref:
        thumbnail_path = Path(payload.thumbnail_ref)
        if thumbnail_path.exists() and thumbnail_path.suffix == ".json":
            thumbnail_signal = json.loads(thumbnail_path.read_text(encoding="utf-8"))

    saturation = float(thumbnail_signal.get("saturation", 0.18 + summary["token_hits"] * 0.12))
    contrast = float(thumbnail_signal.get("contrast", 0.22 + summary["token_hits"] * 0.1))
    text_density = float(
        thumbnail_signal.get("text_density", 0.12 + min(summary["title_length"] / 120.0, 0.3))
    )
    face_emphasis = float(thumbnail_signal.get("face_emphasis", 0.08 + summary["token_hits"] * 0.11))
    shock_indicator = float(
        thumbnail_signal.get("shock_indicator", 0.07 + summary["token_hits"] * 0.14)
    )
    summary.update(
        {
            "thumbnail_saturation": round(saturation, 4),
            "thumbnail_contrast": round(contrast, 4),
            "thumbnail_text_density": round(text_density, 4),
            "thumbnail_face_emphasis": round(face_emphasis, 4),
            "thumbnail_shock_indicator": round(shock_indicator, 4),
        }
    )
    return [saturation, contrast, text_density, face_emphasis, shock_indicator]


def _metadata_vector(payload: ScoreItemRequest, summary: dict[str, float]) -> list[float]:
    view_count = float(payload.metadata.view_count or 0)
    like_count = float(payload.metadata.like_count or 0)
    duration_seconds = float(payload.metadata.duration_seconds or 0)
    like_ratio = like_count / max(view_count, 1.0)
    prior_flags = float(payload.channel.prior_flags)
    channel_risk_mean = round(min(0.2 + (prior_flags * 0.12), 0.95), 4)
    summary.update(
        {
            "view_count_log": round(math.log1p(view_count), 4),
            "like_ratio": round(like_ratio, 4),
            "duration_seconds": duration_seconds,
            "prior_flags": prior_flags,
            "channel_risk_mean": channel_risk_mean,
        }
    )
    return [
        summary["title_length"],
        summary["uppercase_ratio"],
        summary["token_hits"],
        prior_flags,
        channel_risk_mean,
        duration_seconds,
        math.log1p(view_count),
        like_ratio,
    ]


def _bootstrap_signals(payload: ScoreItemRequest) -> ModelSignals:
    summary = _title_summary(payload)
    _vision_vector(payload, summary)
    _metadata_vector(payload, summary)
    text_score = min(0.12 + summary["token_hits"] * 0.18 + summary["uppercase_ratio"] * 0.2, 0.98)
    vision_score = min(
        0.1 + summary["thumbnail_shock_indicator"] * 0.42 + summary["thumbnail_saturation"] * 0.18,
        0.98,
    )
    metadata_score = min(
        0.08
        + summary["prior_flags"] * 0.06
        + summary["like_ratio"] * 0.25
        + summary["thumbnail_text_density"] * 0.22,
        0.98,
    )
    fusion_score = round((text_score * 0.44) + (vision_score * 0.32) + (metadata_score * 0.24), 4)
    confidence = round(min(0.52 + fusion_score * 0.43, 0.97), 4)
    uncertainty = round(max(0.03, 1.0 - confidence), 4)
    return ModelSignals(
        text_score=round(text_score, 4),
        vision_score=round(vision_score, 4),
        metadata_score=round(metadata_score, 4),
        fusion_score=fusion_score,
        calibrated_score=fusion_score,
        confidence=confidence,
        uncertainty=uncertainty,
        model_version="bootstrap-v0",
        mode="bootstrap",
        feature_summary=summary,
    )


def predict_item_signals(payload: ScoreItemRequest) -> ModelSignals:
    bundle = load_model_bundle()
    if bundle is None:
        return _bootstrap_signals(payload)

    summary = _title_summary(payload)
    text_matrix = bundle["text_vectorizer"].transform([payload.title])
    vision_vector = np.asarray([_vision_vector(payload, summary)], dtype=float)
    metadata_vector = np.asarray([_metadata_vector(payload, summary)], dtype=float)

    text_score = _safe_probability(bundle["text_model"], text_matrix)
    vision_score = _safe_probability(bundle["vision_model"], vision_vector)
    metadata_score = _safe_probability(bundle["metadata_model"], metadata_vector)
    fusion_features = np.asarray([[text_score, vision_score, metadata_score]], dtype=float)
    fusion_score = _safe_probability(bundle["fusion_model"], fusion_features)
    calibration_model = bundle.get("calibration_model")
    calibrated_score = (
        _safe_probability(calibration_model, np.asarray([[fusion_score]], dtype=float))
        if calibration_model is not None
        else fusion_score
    )
    confidence = round(min(0.58 + calibrated_score * 0.38, 0.98), 4)
    uncertainty = round(max(0.02, 1.0 - confidence), 4)
    model_info = load_model_info()
    return ModelSignals(
        text_score=round(text_score, 4),
        vision_score=round(vision_score, 4),
        metadata_score=round(metadata_score, 4),
        fusion_score=round(fusion_score, 4),
        calibrated_score=round(calibrated_score, 4),
        confidence=confidence,
        uncertainty=uncertainty,
        model_version=str(model_info.get("model_version", "baseline-v1")),
        mode="trained",
        feature_summary=summary,
    )


def describe_model() -> dict[str, Any]:
    model_info = load_model_info()
    bundle = load_model_bundle()
    if bundle is None:
        return {"mode": "bootstrap", **model_info}
    return {
        "mode": "trained",
        **model_info,
        "available_heads": ["text", "vision", "metadata", "fusion", "calibration"],
    }
