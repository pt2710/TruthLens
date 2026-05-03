from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

import numpy as np

from truthlens_feature_extractors import (
    build_bias_primitives,
    build_bias_profile,
    count_sensational_tokens,
    extract_thumbnail_features,
    infer_bseo_prior_frames,
    infer_content_taxonomy,
    thumbnail_array_from_path,
    sentence_transformer_matrix,
    transcript_mismatch_score,
    transcript_overlap,
    uppercase_ratio,
)
from truthlens_model_serving.registry import load_model_bundle, load_model_info
from truthlens_model_serving.semantic_router import (
    AdaptiveSemanticEvidenceRouter,
    route_adjusted_mismatch,
)
from truthlens_model_serving.temporal import (
    CHANNEL_SEQUENCE_FEATURE_NAMES,
    temporal_artifacts_from_payload,
    temporal_history_scores_from_artifacts,
)
from truthlens_model_serving.vae import (
    PACKAGING_VAE_FEATURE_NAMES,
    artifacts_from_payload,
    packaging_anomaly_from_artifacts,
)
from truthlens_model_serving.vision import (
    thumbnail_scores_from_artifacts,
    vision_artifacts_from_payload,
)
from truthlens_shared_schemas.contracts import ScoreItemRequest


_SEMANTIC_ROUTER = AdaptiveSemanticEvidenceRouter()


@dataclass(slots=True)
class ModelSignals:
    text_score: float
    vision_score: float
    metadata_score: float
    history_score: float
    anomaly_score: float
    fusion_score: float
    calibrated_score: float
    confidence: float
    uncertainty: float
    model_version: str
    mode: str
    feature_summary: dict[str, Any]


VISION_FEATURE_NAMES = [
    "thumbnail_brightness",
    "thumbnail_saturation",
    "thumbnail_contrast",
    "thumbnail_text_density",
    "thumbnail_entropy",
    "thumbnail_aspect_ratio",
    "thumbnail_face_emphasis",
    "thumbnail_shock_indicator",
    "transcript_mismatch_score",
    "thumbnail_byte_size",
    "prior_flags",
    "estimated_risk_seed",
]

METADATA_FEATURE_NAMES = [
    "title_length",
    "uppercase_ratio",
    "token_hits",
    "prior_flags",
    "channel_risk_mean",
    "duration_seconds",
    "view_count_log",
    "like_ratio",
    "transcript_mismatch_score",
]

HISTORY_FEATURE_NAMES = [
    "prior_flags",
    "channel_risk_mean",
    "repeat_template_rate",
    "recent_upload_velocity",
    "engagement_anomaly",
]

FUSION_FEATURE_NAMES = [
    "text_score",
    "vision_score",
    "metadata_score",
    "history_score",
    "anomaly_score",
]

MUSIC_TITLE_MARKERS = (
    "official audio",
    "official video",
    "music video",
    "lyric video",
    "lyrics",
    "visualizer",
    "visualiser",
    "remix",
    "cover",
    "instrumental",
    "live session",
    "live performance",
    "single",
    "album track",
    "feat.",
    " ft.",
)

MUSIC_CHANNEL_MARKERS = (
    "records",
    "music",
    "vevo",
    "topic",
    "beats",
    "orchestra",
    "choir",
    "band",
    "artist",
)

MUSIC_TRANSCRIPT_MARKERS = (
    "chorus",
    "verse",
    "refrain",
    "bridge",
    "lyrics",
    "♪",
)

NON_MUSIC_MARKERS = (
    "trailer",
    "review",
    "documentary",
    "tutorial",
    "interview",
    "podcast",
    "news",
    "update",
    "walkthrough",
    "gameplay",
    "reaction",
)


def _safe_probability(model: Any, matrix: Any) -> float:
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(matrix)
        return float(probabilities[0][1])
    prediction = model.predict(matrix)
    return float(prediction[0])


def _top_dense_contributors(
    model: Any,
    feature_names: list[str],
    vector: np.ndarray,
    *,
    limit: int = 3,
) -> list[dict[str, float | str]]:
    if not hasattr(model, "coef_"):
        return []
    coefficients = np.asarray(model.coef_[0], dtype=float)
    values = np.asarray(vector, dtype=float).ravel()
    contributors: list[dict[str, float | str]] = []
    for index, feature_name in enumerate(feature_names):
        if index >= len(coefficients) or index >= len(values):
            break
        contribution = float(coefficients[index] * values[index])
        if contribution <= 0:
            continue
        contributors.append(
            {
                "name": feature_name,
                "contribution": round(contribution, 4),
                "value": round(float(values[index]), 4),
            }
        )
    contributors.sort(key=lambda item: float(item["contribution"]), reverse=True)
    return contributors[:limit]


def _dense_counterfactuals(
    model: Any,
    feature_names: list[str],
    vector: np.ndarray,
    *,
    limit: int = 2,
) -> list[dict[str, float | str]]:
    if not hasattr(model, "predict_proba"):
        return []
    baseline = _safe_probability(model, vector.reshape(1, -1))
    counterfactuals: list[dict[str, float | str]] = []
    for index, feature_name in enumerate(feature_names):
        ablated = np.asarray(vector, dtype=float).copy()
        if index >= ablated.shape[0]:
            continue
        ablated[index] = 0.0
        score = _safe_probability(model, ablated.reshape(1, -1))
        score_drop = round(max(baseline - score, 0.0), 4)
        if score_drop <= 0:
            continue
        counterfactuals.append({"name": feature_name, "score_drop": score_drop})
    counterfactuals.sort(key=lambda item: float(item["score_drop"]), reverse=True)
    return counterfactuals[:limit]


def _top_anomaly_contributors(
    feature_names: list[str],
    feature_errors: np.ndarray,
    *,
    limit: int = 3,
) -> list[dict[str, float | str]]:
    values = np.asarray(feature_errors, dtype=float).ravel()
    contributors: list[dict[str, float | str]] = []
    for index, feature_name in enumerate(feature_names):
        if index >= len(values):
            break
        contribution = float(values[index])
        if contribution <= 0:
            continue
        contributors.append(
            {
                "name": feature_name,
                "contribution": round(contribution, 4),
            }
        )
    contributors.sort(key=lambda item: float(item["contribution"]), reverse=True)
    return contributors[:limit]


def _top_text_contributors(
    model: Any,
    vectorizer: Any,
    matrix: Any,
    *,
    limit: int = 3,
) -> list[dict[str, float | str]]:
    if not hasattr(model, "coef_") or not hasattr(matrix, "tocoo"):
        return []
    coefficients = np.asarray(model.coef_[0], dtype=float)
    feature_names = vectorizer.get_feature_names_out()
    row = matrix.tocoo()
    contributors: list[dict[str, float | str]] = []
    for column, value in zip(row.col.tolist(), row.data.tolist()):
        if column >= len(coefficients):
            continue
        contribution = float(coefficients[column] * value)
        if contribution <= 0:
            continue
        contributors.append(
            {
                "name": str(feature_names[column]),
                "contribution": round(contribution, 4),
                "value": round(float(value), 4),
            }
        )
    contributors.sort(key=lambda item: float(item["contribution"]), reverse=True)
    return contributors[:limit]


def _text_encoder_resolution(bundle: dict[str, Any], model_info: dict[str, Any]) -> dict[str, Any]:
    payload = bundle.get("text_encoder_resolution")
    if isinstance(payload, dict):
        return payload
    payload = model_info.get("text_encoder_resolution")
    if isinstance(payload, dict):
        return payload
    return {"actual_encoder": "count-vectorizer-bigrams"}


def _history_encoder_resolution(bundle: dict[str, Any], model_info: dict[str, Any]) -> dict[str, Any]:
    payload = bundle.get("history_encoder_resolution")
    if isinstance(payload, dict):
        return payload
    payload = model_info.get("history_encoder_resolution")
    if isinstance(payload, dict):
        return payload
    return {
        "actual_encoder": "sequence-summary-v1",
        "sequence_length": 4,
        "hidden_dim": 16,
        "num_layers": 1,
    }


def _vision_encoder_resolution(bundle: dict[str, Any], model_info: dict[str, Any]) -> dict[str, Any]:
    payload = bundle.get("vision_encoder_resolution")
    if isinstance(payload, dict):
        return payload
    payload = model_info.get("vision_encoder_resolution")
    if isinstance(payload, dict):
        return payload
    return {
        "actual_encoder": "vision-v2",
        "image_size": 32,
        "conv_channels": [8, 16],
        "hidden_dim": 32,
        "patch_size": 8,
        "transformer_hidden_size": 64,
        "transformer_num_hidden_layers": 2,
        "transformer_num_attention_heads": 4,
        "transformer_intermediate_size": 128,
        "transformer_pooling": "cls",
    }


def _text_matrix(payload: ScoreItemRequest, bundle: dict[str, Any], model_info: dict[str, Any]) -> Any:
    resolution = _text_encoder_resolution(bundle, model_info)
    actual_encoder = str(resolution.get("actual_encoder", "count-vectorizer-bigrams"))
    if actual_encoder == "sentence-transformer":
        model_name = str(resolution.get("sentence_transformer_model", "")).strip()
        return sentence_transformer_matrix([payload.title], model_name)
    text_vectorizer = bundle.get("text_vectorizer")
    if text_vectorizer is None:
        raise ValueError("Sparse text vectorizer is missing from the trained model bundle.")
    return text_vectorizer.transform([payload.title])


def _runtime_safe_head_fallbacks_enabled() -> bool:
    override = os.getenv("TRUTHLENS_RUNTIME_SAFE_HEAD_FALLBACKS", "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    return os.getenv("TRUTHLENS_ENV", "").strip().lower() == "beta"


def _title_summary(payload: ScoreItemRequest) -> dict[str, Any]:
    title = payload.title
    token_hits = count_sensational_tokens(title)
    return {
        "token_hits": float(token_hits),
        "title_length": float(len(title)),
        "uppercase_ratio": uppercase_ratio(title),
    }


def _count_phrase_hits(text: str, phrases: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for phrase in phrases if phrase in lowered)


def _music_context(payload: ScoreItemRequest, summary: dict[str, Any]) -> float:
    history = dict(payload.channel.channel_history_features)
    history.setdefault("prior_flags", float(payload.channel.prior_flags))
    taxonomy = infer_content_taxonomy(
        title=payload.title,
        description=payload.description_snapshot,
        transcript=payload.transcript_excerpt,
        channel_name=payload.channel.channel_name,
        channel_history_features=history,
    )
    summary["music_likelihood"] = float(taxonomy["music_likelihood"])
    summary["content_class"] = str(taxonomy["content_class"])
    summary["content_class_confidence"] = float(taxonomy["content_class_confidence"])
    summary["content_class_scores"] = dict(taxonomy["content_class_scores"])
    summary["taxonomy_guardrail"] = str(taxonomy["guardrail"])
    summary["music_title_hits"] = float(_count_phrase_hits(payload.title.lower(), MUSIC_TITLE_MARKERS))
    summary["music_channel_hits"] = float(
        _count_phrase_hits(payload.channel.channel_name.lower(), MUSIC_CHANNEL_MARKERS)
    )
    summary["music_transcript_hits"] = float(
        _count_phrase_hits((payload.transcript_excerpt or "").lower(), MUSIC_TRANSCRIPT_MARKERS)
    )
    return float(taxonomy["music_likelihood"])


def _refresh_semantic_route(payload: ScoreItemRequest, summary: dict[str, Any]) -> dict[str, Any]:
    route = _SEMANTIC_ROUTER.route(payload, summary).to_payload()
    summary["semantic_evidence_route"] = route
    summary["runtime_route"] = route["runtime_route"]
    summary["learning_capture_plan"] = route["learning_capture_plan"]
    summary["adversarial_guard"] = route["adversarial_guard"]
    summary["mismatch_pressure"] = route["mismatch_pressure"]
    return route


def _semantic_route_allows_remote_thumbnail_fetch(
    payload: ScoreItemRequest,
    summary: dict[str, Any],
) -> bool:
    route = dict(summary.get("semantic_evidence_route", {}))
    if not str(payload.thumbnail_ref or "").startswith(("http://", "https://")):
        return True
    return not (
        route.get("runtime_route") == "minimal_creative"
        and route.get("adversarial_guard") == "clean"
    )


def _transcript_mismatch(payload: ScoreItemRequest, summary: dict[str, Any]) -> float:
    transcript = payload.transcript_excerpt or ""
    if not transcript:
        summary["transcript_title_overlap"] = 0.0
        summary["raw_transcript_mismatch_score"] = 0.0
        summary["transcript_mismatch_score"] = 0.0
        return 0.0

    overlap = transcript_overlap(payload.title, transcript)
    raw_mismatch = transcript_mismatch_score(payload.title, transcript, summary["token_hits"])
    mismatch, guardrail = route_adjusted_mismatch(
        raw_mismatch,
        str(summary.get("content_class", "unknown")),
        dict(summary.get("semantic_evidence_route", {})),
    )
    summary["transcript_title_overlap"] = round(overlap, 4)
    summary["raw_transcript_mismatch_score"] = round(raw_mismatch, 4)
    summary["transcript_mismatch_score"] = round(mismatch, 4)
    summary["taxonomy_guardrail"] = guardrail
    return mismatch


def _bias_profile_summary(
    payload: ScoreItemRequest,
    summary: dict[str, Any],
    *,
    uncertainty: float,
) -> dict[str, Any]:
    metrics = build_bias_primitives(
        title=payload.title,
        description=payload.description_snapshot,
        transcript=payload.transcript_excerpt,
        channel_name=payload.channel.channel_name,
        raw_transcript_mismatch=float(summary.get("raw_transcript_mismatch_score", 0.0)),
        adjusted_transcript_mismatch=float(summary.get("transcript_mismatch_score", 0.0)),
        content_class=str(summary.get("content_class", "unknown")),
        content_class_confidence=float(summary.get("content_class_confidence", 0.0)),
        prior_flags=int(payload.channel.prior_flags),
        channel_risk_mean=float(summary.get("channel_risk_mean", 0.0)),
        repeat_template_rate=float(summary.get("repeat_template_rate", 0.0)),
        channel_history_features=dict(payload.channel.channel_history_features),
        uncertainty=uncertainty,
    )
    prior_frames = infer_bseo_prior_frames(
        title=payload.title,
        description=payload.description_snapshot,
        transcript=payload.transcript_excerpt,
        channel_name=payload.channel.channel_name,
        content_class=str(summary.get("content_class", "unknown")),
        content_class_confidence=float(summary.get("content_class_confidence", 0.0)),
        metrics=metrics,
        prior_flags=int(payload.channel.prior_flags),
        channel_risk_mean=float(summary.get("channel_risk_mean", 0.0)),
        repeat_template_rate=float(summary.get("repeat_template_rate", 0.0)),
        channel_history_features=dict(payload.channel.channel_history_features),
        thumbnail_text_density=float(summary.get("thumbnail_text_density", 0.0)),
        thumbnail_shock_indicator=float(summary.get("thumbnail_shock_indicator", 0.0)),
    )
    profile = build_bias_profile(
        metrics=metrics,
        content_class=str(summary.get("content_class", "unknown")),
        content_class_confidence=float(summary.get("content_class_confidence", 0.0)),
        raw_transcript_mismatch=float(summary.get("raw_transcript_mismatch_score", 0.0)),
        adjusted_transcript_mismatch=float(summary.get("transcript_mismatch_score", 0.0)),
        title=payload.title,
        description=payload.description_snapshot,
        transcript=payload.transcript_excerpt,
        channel_name=payload.channel.channel_name,
        prior_flags=int(payload.channel.prior_flags),
        channel_risk_mean=float(summary.get("channel_risk_mean", 0.0)),
        repeat_template_rate=float(summary.get("repeat_template_rate", 0.0)),
        channel_history_features=dict(payload.channel.channel_history_features),
        thumbnail_text_density=float(summary.get("thumbnail_text_density", 0.0)),
        thumbnail_shock_indicator=float(summary.get("thumbnail_shock_indicator", 0.0)),
        prior_frames=prior_frames,
        uncertainty=uncertainty,
    )
    summary["bias_primitives"] = metrics
    summary["bias_profile"] = profile
    summary["dominant_bias_risk"] = str(profile.get("dominant_bias", "balanced-context"))
    summary["bseo_positive_contexts"] = list(prior_frames["positive_contexts"])
    summary["bseo_negative_contexts"] = list(prior_frames["negative_contexts"])
    summary["bseo_parameter_frames"] = dict(prior_frames["parameter_frames"])
    return profile


def _vision_vector(
    payload: ScoreItemRequest,
    summary: dict[str, Any],
    *,
    allow_remote_thumbnail_fetch: bool = True,
) -> list[float]:
    thumbnail_signal: dict[str, float] = {}
    if payload.thumbnail_ref:
        thumbnail_path = Path(payload.thumbnail_ref)
        if thumbnail_path.exists() and thumbnail_path.suffix == ".json":
            thumbnail_signal = json.loads(thumbnail_path.read_text(encoding="utf-8"))
        elif thumbnail_path.exists():
            extracted = extract_thumbnail_features(thumbnail_path)
            thumbnail_signal = {
                "brightness": extracted.get("thumbnail_brightness", 0.45),
                "saturation": extracted.get("thumbnail_saturation", 0.3),
                "contrast": extracted.get("thumbnail_contrast", 0.35),
                "text_density": extracted.get("thumbnail_text_density", 0.18),
                "face_emphasis": extracted.get("thumbnail_face_emphasis", 0.12),
                "shock_indicator": extracted.get("thumbnail_shock_indicator", 0.15),
                "entropy": extracted.get("thumbnail_entropy", 0.4),
                "aspect_ratio": extracted.get("thumbnail_aspect_ratio", (16 / 9) / 2.5),
                "byte_size": extracted.get("thumbnail_byte_size", 0.0),
            }
        elif payload.thumbnail_ref.startswith(("http://", "https://")) and allow_remote_thumbnail_fetch:
            try:
                parsed = urlparse(payload.thumbnail_ref)
                suffix = Path(parsed.path).suffix or ".jpg"
                with urlopen(payload.thumbnail_ref, timeout=6.0) as response:
                    image_bytes = response.read()
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                    handle.write(image_bytes)
                    temp_path = Path(handle.name)
                try:
                    extracted = extract_thumbnail_features(temp_path)
                finally:
                    temp_path.unlink(missing_ok=True)
                thumbnail_signal = {
                    "brightness": extracted.get("thumbnail_brightness", 0.45),
                    "saturation": extracted.get("thumbnail_saturation", 0.3),
                    "contrast": extracted.get("thumbnail_contrast", 0.35),
                    "text_density": extracted.get("thumbnail_text_density", 0.18),
                    "face_emphasis": extracted.get("thumbnail_face_emphasis", 0.12),
                    "shock_indicator": extracted.get("thumbnail_shock_indicator", 0.15),
                    "entropy": extracted.get("thumbnail_entropy", 0.4),
                    "aspect_ratio": extracted.get("thumbnail_aspect_ratio", (16 / 9) / 2.5),
                    "byte_size": extracted.get("thumbnail_byte_size", 0.0),
                }
            except OSError:
                thumbnail_signal = {}
        elif payload.thumbnail_ref.startswith(("http://", "https://")):
            summary["thumbnail_remote_fetch_skipped_reason"] = (
                "Adaptive semantic routing kept clean creative content on the minimal runtime route."
            )

    brightness = float(thumbnail_signal.get("brightness", 0.42))
    saturation = float(thumbnail_signal.get("saturation", 0.18 + summary["token_hits"] * 0.12))
    contrast = float(thumbnail_signal.get("contrast", 0.22 + summary["token_hits"] * 0.1))
    text_density = float(
        thumbnail_signal.get("text_density", 0.12 + min(summary["title_length"] / 120.0, 0.3))
    )
    face_emphasis = float(thumbnail_signal.get("face_emphasis", 0.08 + summary["token_hits"] * 0.11))
    shock_indicator = float(
        thumbnail_signal.get("shock_indicator", 0.07 + summary["token_hits"] * 0.14)
    )
    entropy = float(thumbnail_signal.get("entropy", 0.4))
    aspect_ratio = float(thumbnail_signal.get("aspect_ratio", (16 / 9) / 2.5))
    byte_size = float(thumbnail_signal.get("byte_size", 0.0)) / 100000.0
    prior_flags = float(payload.channel.prior_flags)
    estimated_risk_seed = min(
        0.98,
        max(
            0.08,
            (shock_indicator * 0.5)
            + (saturation * 0.25)
            + (text_density * 0.15)
            + (summary.get("transcript_mismatch_score", 0.0) * 0.1),
        ),
    )
    summary.update(
        {
            "thumbnail_brightness": round(brightness, 4),
            "thumbnail_saturation": round(saturation, 4),
            "thumbnail_contrast": round(contrast, 4),
            "thumbnail_text_density": round(text_density, 4),
            "thumbnail_face_emphasis": round(face_emphasis, 4),
            "thumbnail_shock_indicator": round(shock_indicator, 4),
            "thumbnail_entropy": round(entropy, 4),
            "thumbnail_aspect_ratio": round(aspect_ratio, 4),
            "thumbnail_byte_size": round(byte_size * 100000.0, 4),
            "estimated_risk_seed": round(estimated_risk_seed, 4),
        }
    )
    return [
        brightness,
        saturation,
        contrast,
        text_density,
        entropy,
        aspect_ratio,
        face_emphasis,
        shock_indicator,
        summary.get("transcript_mismatch_score", 0.0),
        byte_size,
        prior_flags,
        estimated_risk_seed,
    ]


def _thumbnail_image_from_ref(
    thumbnail_ref: str | None,
    *,
    image_size: int,
) -> np.ndarray | None:
    if not thumbnail_ref:
        return None
    thumbnail_path = Path(thumbnail_ref)
    if thumbnail_path.exists():
        return thumbnail_array_from_path(thumbnail_path, image_size=image_size)
    if not thumbnail_ref.startswith(("http://", "https://")):
        return None
    try:
        parsed = urlparse(thumbnail_ref)
        suffix = Path(parsed.path).suffix or ".jpg"
        with urlopen(thumbnail_ref, timeout=6.0) as response:
            image_bytes = response.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(image_bytes)
            temp_path = Path(handle.name)
        try:
            return thumbnail_array_from_path(temp_path, image_size=image_size)
        finally:
            temp_path.unlink(missing_ok=True)
    except OSError:
        return None


def _metadata_vector(payload: ScoreItemRequest, summary: dict[str, Any]) -> list[float]:
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
        summary.get("transcript_mismatch_score", 0.0),
    ]


def _history_vector(payload: ScoreItemRequest, summary: dict[str, Any]) -> list[float]:
    history = payload.channel.channel_history_features
    prior_flags = float(payload.channel.prior_flags)
    channel_risk_mean = float(history.get("channel_risk_mean", min(0.18 + prior_flags * 0.12, 0.95)))
    repeat_template_rate = float(history.get("repeat_template_rate", min(0.12 + prior_flags * 0.08, 0.92)))
    recent_upload_velocity = float(
        history.get("recent_upload_velocity", history.get("publishing_velocity", 0.18 + prior_flags * 0.05))
    )
    engagement_anomaly = float(history.get("engagement_anomaly", 1.0 + prior_flags * 0.06))
    summary.update(
        {
            "channel_risk_mean": round(channel_risk_mean, 4),
            "repeat_template_rate": round(repeat_template_rate, 4),
            "recent_upload_velocity": round(recent_upload_velocity, 4),
            "engagement_anomaly": round(engagement_anomaly, 4),
        }
    )
    return [
        prior_flags,
        channel_risk_mean,
        repeat_template_rate,
        recent_upload_velocity,
        engagement_anomaly,
    ]


def _history_sequence_row(
    payload: ScoreItemRequest,
    summary: dict[str, Any],
    *,
    decay: float,
) -> list[float]:
    return [
        round(float(summary.get("estimated_risk_seed", 0.0)) * decay, 4),
        round(float(summary.get("transcript_mismatch_score", 0.0)) * decay, 4),
        round(float(summary.get("token_hits", 0.0)) * decay, 4),
        round(float(summary.get("repeat_template_rate", 0.0)) * decay, 4),
        round(float(summary.get("recent_upload_velocity", 0.0)) * decay, 4),
        round(1.0 + max(float(summary.get("engagement_anomaly", 1.0)) - 1.0, 0.0) * decay, 4),
        round(float(summary.get("like_ratio", 0.0)) * decay, 4),
    ]


def _history_sequence_from_payload(
    payload: ScoreItemRequest,
    summary: dict[str, Any],
    *,
    sequence_length: int,
) -> np.ndarray:
    history = payload.channel.channel_history_features
    explicit_rows: list[list[float]] = []
    for step in range(sequence_length):
        prefix = f"sequence_step_{step}_"
        if all(f"{prefix}{feature}" in history for feature in CHANNEL_SEQUENCE_FEATURE_NAMES):
            explicit_rows.append(
                [float(history[f"{prefix}{feature}"]) for feature in CHANNEL_SEQUENCE_FEATURE_NAMES]
            )
    if explicit_rows:
        summary["history_sequence_mode"] = "explicit-sequence"
        rows = explicit_rows[-sequence_length:]
        return np.asarray(rows, dtype=float).reshape(1, len(rows), len(CHANNEL_SEQUENCE_FEATURE_NAMES))

    rows = []
    for offset in range(sequence_length):
        age = sequence_length - offset - 1
        decay = max(0.25, 1.0 - age * 0.18)
        rows.append(_history_sequence_row(payload, summary, decay=decay))
    summary["history_sequence_mode"] = "summary-proxy"
    return np.asarray(rows, dtype=float).reshape(1, sequence_length, len(CHANNEL_SEQUENCE_FEATURE_NAMES))


def _packaging_vector(
    vision_vector: list[float],
    metadata_vector: list[float],
) -> list[float]:
    return [
        float(vision_vector[0]),
        float(vision_vector[1]),
        float(vision_vector[2]),
        float(vision_vector[3]),
        float(vision_vector[4]),
        float(vision_vector[5]),
        float(vision_vector[6]),
        float(vision_vector[7]),
        float(vision_vector[8]),
        float(vision_vector[9]),
        float(vision_vector[10]),
        float(vision_vector[11]),
        float(metadata_vector[0]),
        float(metadata_vector[1]),
        float(metadata_vector[2]),
        float(metadata_vector[4]),
        float(metadata_vector[5]),
        float(metadata_vector[6]),
        float(metadata_vector[7]),
        float(metadata_vector[8]),
    ]


def _bootstrap_signals(payload: ScoreItemRequest) -> ModelSignals:
    summary = _title_summary(payload)
    _music_context(payload, summary)
    initial_route = _refresh_semantic_route(payload, summary)
    _transcript_mismatch(payload, summary)
    vision_vector = _vision_vector(
        payload,
        summary,
        allow_remote_thumbnail_fetch=_semantic_route_allows_remote_thumbnail_fetch(payload, summary),
    )
    updated_route = _refresh_semantic_route(payload, summary)
    if updated_route != initial_route:
        _transcript_mismatch(payload, summary)
    metadata_vector = _metadata_vector(payload, summary)
    _history_vector(payload, summary)
    text_score = min(0.12 + summary["token_hits"] * 0.18 + summary["uppercase_ratio"] * 0.2, 0.98)
    vision_score = min(
        0.1 + summary["thumbnail_shock_indicator"] * 0.42 + summary["thumbnail_saturation"] * 0.18,
        0.98,
    )
    metadata_score = min(
        0.08
        + summary["prior_flags"] * 0.06
        + summary["like_ratio"] * 0.25
        + summary["thumbnail_text_density"] * 0.22
        + summary.get("transcript_mismatch_score", 0.0) * 0.18,
        0.98,
    )
    history_score = min(
        0.08
        + summary["channel_risk_mean"] * 0.38
        + summary["repeat_template_rate"] * 0.24
        + max(summary["engagement_anomaly"] - 1.0, 0.0) * 0.08,
        0.98,
    )
    packaging_vector = _packaging_vector(vision_vector, metadata_vector)
    anomaly_score = min(
        0.08
        + max(float(packaging_vector[7]), 0.0) * 0.18
        + max(float(packaging_vector[8]), 0.0) * 0.26
        + max(float(packaging_vector[15]), 0.0) * 0.1
        + max(float(packaging_vector[18]) - 0.12, 0.0) * 0.25,
        0.98,
    )
    fusion_score = round(
        (text_score * 0.28)
        + (vision_score * 0.22)
        + (metadata_score * 0.17)
        + (history_score * 0.18)
        + (anomaly_score * 0.15),
        4,
    )
    confidence = round(min(0.52 + fusion_score * 0.43, 0.97), 4)
    uncertainty = round(max(0.03, 1.0 - confidence), 4)
    _bias_profile_summary(payload, summary, uncertainty=uncertainty)
    return ModelSignals(
        text_score=round(text_score, 4),
        vision_score=round(vision_score, 4),
        metadata_score=round(metadata_score, 4),
        history_score=round(history_score, 4),
        anomaly_score=round(anomaly_score, 4),
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
    _music_context(payload, summary)
    initial_route = _refresh_semantic_route(payload, summary)
    _transcript_mismatch(payload, summary)
    model_info = load_model_info()
    text_resolution = _text_encoder_resolution(bundle, model_info)
    vision_resolution = _vision_encoder_resolution(bundle, model_info)
    history_resolution = _history_encoder_resolution(bundle, model_info)
    summary["text_encoder_actual"] = str(text_resolution.get("actual_encoder", "count-vectorizer-bigrams"))
    summary["text_encoder_requested"] = str(
        text_resolution.get("requested_encoder", summary["text_encoder_actual"])
    )
    summary["vision_encoder_actual"] = str(vision_resolution.get("actual_encoder", "vision-v2"))
    summary["vision_encoder_requested"] = str(
        vision_resolution.get("requested_encoder", summary["vision_encoder_actual"])
    )
    summary["history_encoder_actual"] = str(history_resolution.get("actual_encoder", "sequence-summary-v1"))
    summary["history_encoder_requested"] = str(
        history_resolution.get("requested_encoder", summary["history_encoder_actual"])
    )
    runtime_safe_fallbacks = _runtime_safe_head_fallbacks_enabled()
    text_runtime_fallback = runtime_safe_fallbacks and summary["text_encoder_actual"] == "sentence-transformer"
    vision_runtime_fallback = runtime_safe_fallbacks and summary["vision_encoder_actual"] in {
        "tiny-cnn-thumbnail",
        "vision-transformer",
    }
    history_runtime_fallback = runtime_safe_fallbacks and summary["history_encoder_actual"] == "lstm-sequence"
    if text_resolution.get("fallback_reason"):
        summary["text_encoder_fallback_reason"] = str(text_resolution["fallback_reason"])
    if vision_resolution.get("fallback_reason"):
        summary["vision_encoder_fallback_reason"] = str(vision_resolution["fallback_reason"])
    if history_resolution.get("fallback_reason"):
        summary["history_encoder_fallback_reason"] = str(history_resolution["fallback_reason"])
    if text_runtime_fallback:
        summary["text_encoder_runtime_fallback_reason"] = (
            "Hosted beta disables sentence-transformer inference in the scoring hot path."
        )
    if vision_runtime_fallback:
        summary["vision_encoder_runtime_fallback_reason"] = (
            "Hosted beta keeps the engineered vision head in the scoring hot path."
        )
    if history_runtime_fallback:
        summary["history_encoder_runtime_fallback_reason"] = (
            "Hosted beta disables temporal sequence inference in the scoring hot path."
        )

    bootstrap = _bootstrap_signals(payload)
    try:
        text_matrix = None
        text_score = bootstrap.text_score
        if not text_runtime_fallback:
            text_matrix = _text_matrix(payload, bundle, model_info)
            text_score = _safe_probability(bundle["text_model"], text_matrix)
        vision_values = _vision_vector(
            payload,
            summary,
            allow_remote_thumbnail_fetch=_semantic_route_allows_remote_thumbnail_fetch(payload, summary),
        )
        updated_route = _refresh_semantic_route(payload, summary)
        if updated_route != initial_route:
            _transcript_mismatch(payload, summary)
        metadata_values = _metadata_vector(payload, summary)
        history_values = _history_vector(payload, summary)
        packaging_values = _packaging_vector(vision_values, metadata_values)
        vision_vector = np.asarray([vision_values], dtype=float)
        metadata_vector = np.asarray([metadata_values], dtype=float)
        history_vector = np.asarray([history_values], dtype=float)
        packaging_vector = np.asarray([packaging_values], dtype=float)
        vision_score = _safe_probability(bundle["vision_model"], vision_vector)
        vision_used_learned_encoder = False
        if (
            not vision_runtime_fallback
            and summary["vision_encoder_actual"] in {"tiny-cnn-thumbnail", "vision-transformer"}
        ):
            vision_payload = bundle.get("vision_encoder_artifacts")
            if isinstance(vision_payload, dict):
                vision_artifacts = vision_artifacts_from_payload(vision_payload)
                thumbnail_image = (
                    _thumbnail_image_from_ref(
                        payload.thumbnail_ref,
                        image_size=vision_artifacts.image_size,
                    )
                    if _semantic_route_allows_remote_thumbnail_fetch(payload, summary)
                    else None
                )
                if thumbnail_image is not None:
                    vision_score = float(
                        thumbnail_scores_from_artifacts(
                            np.asarray([thumbnail_image], dtype=np.float32),
                            vision_artifacts,
                        )[0]
                    )
                    vision_used_learned_encoder = True
                    summary["vision_embedding_note"] = (
                        "Vision score came from the optional ViT thumbnail encoder."
                        if summary["vision_encoder_actual"] == "vision-transformer"
                        else "Vision score came from the optional tiny CNN thumbnail encoder."
                    )
                else:
                    summary["vision_encoder_runtime_fallback"] = (
                        "Thumbnail bytes were unavailable at runtime, so the engineered vision head was used."
                    )
        metadata_score = _safe_probability(bundle["metadata_model"], metadata_vector)
        history_model = bundle.get("history_model")
        history_score = bootstrap.history_score
        if history_runtime_fallback:
            if history_model is not None:
                history_score = _safe_probability(history_model, history_vector)
                summary["history_sequence_note"] = (
                    "Hosted beta used the summary-derived history head instead of temporal sequence inference."
                )
        elif summary["history_encoder_actual"] == "lstm-sequence":
            sequence_payload = bundle.get("history_sequence_artifacts")
            if isinstance(sequence_payload, dict):
                history_artifacts = temporal_artifacts_from_payload(sequence_payload)
                history_sequence = _history_sequence_from_payload(
                    payload,
                    summary,
                    sequence_length=history_artifacts.sequence_length,
                )
                history_score = float(
                    temporal_history_scores_from_artifacts(history_sequence, history_artifacts)[0]
                )
                summary["history_sequence_note"] = (
                    "History score came from a temporal LSTM encoder over channel-sequence features."
                    if summary.get("history_sequence_mode") == "explicit-sequence"
                    else "History score came from a temporal LSTM encoder using a summary-derived sequence proxy."
                )
            elif history_model is not None:
                history_score = _safe_probability(history_model, history_vector)
        elif history_model is not None:
            history_score = _safe_probability(history_model, history_vector)
        anomaly_payload = bundle.get("packaging_vae_artifacts")
        if isinstance(anomaly_payload, dict):
            anomaly_artifacts = artifacts_from_payload(anomaly_payload)
            anomaly_vector, feature_errors = packaging_anomaly_from_artifacts(
                packaging_vector,
                anomaly_artifacts,
            )
            anomaly_score = float(anomaly_vector[0])
            summary["anomaly_top_contributors"] = _top_anomaly_contributors(
                list(anomaly_artifacts.feature_names or PACKAGING_VAE_FEATURE_NAMES),
                feature_errors[0],
            )
            summary["anomaly_reconstruction_error"] = round(float(np.mean(feature_errors[0])), 4)
        else:
            anomaly_score = bootstrap.anomaly_score
            summary["anomaly_top_contributors"] = []
        if text_runtime_fallback:
            summary["text_top_contributors"] = []
            summary["text_embedding_note"] = (
                "Hosted beta used the runtime-safe text fallback instead of the sentence-transformer encoder."
            )
        elif summary["text_encoder_actual"] == "count-vectorizer-bigrams" and "text_vectorizer" in bundle:
            summary["text_top_contributors"] = _top_text_contributors(
                bundle["text_model"],
                bundle["text_vectorizer"],
                text_matrix,
            )
        else:
            summary["text_top_contributors"] = []
            summary["text_embedding_note"] = (
                "Text score came from a dense sentence-transformer embedding path, so token-level attribution "
                "is not exposed by the current explanation layer."
            )
        summary["vision_top_contributors"] = (
            []
            if vision_used_learned_encoder
            else _top_dense_contributors(
                bundle["vision_model"],
                VISION_FEATURE_NAMES,
                vision_vector,
            )
        )
        summary["metadata_top_contributors"] = _top_dense_contributors(
            bundle["metadata_model"],
            METADATA_FEATURE_NAMES,
            metadata_vector,
        )
        summary["history_top_contributors"] = (
            _top_dense_contributors(
                history_model,
                HISTORY_FEATURE_NAMES,
                history_vector,
            )
            if history_model is not None and summary["history_encoder_actual"] != "lstm-sequence"
            else []
        )
        fusion_features = np.asarray(
            [[text_score, vision_score, metadata_score, history_score, anomaly_score]],
            dtype=float,
        )
        summary["fusion_top_contributors"] = _top_dense_contributors(
            bundle["fusion_model"],
            FUSION_FEATURE_NAMES,
            fusion_features,
        )
        summary["fusion_counterfactuals"] = _dense_counterfactuals(
            bundle["fusion_model"],
            FUSION_FEATURE_NAMES,
            fusion_features[0],
        )
        fusion_score = _safe_probability(bundle["fusion_model"], fusion_features)
        calibration_model = bundle.get("calibration_model")
        calibrated_score = (
            _safe_probability(calibration_model, np.asarray([[fusion_score]], dtype=float))
            if calibration_model is not None
            else fusion_score
        )
    except (ValueError, RuntimeError, ImportError, ModuleNotFoundError, OSError):
        return bootstrap
    confidence = round(min(0.58 + calibrated_score * 0.38, 0.98), 4)
    uncertainty = round(max(0.02, 1.0 - confidence), 4)
    _bias_profile_summary(payload, summary, uncertainty=uncertainty)
    return ModelSignals(
        text_score=round(text_score, 4),
        vision_score=round(vision_score, 4),
        metadata_score=round(metadata_score, 4),
        history_score=round(history_score, 4),
        anomaly_score=round(anomaly_score, 4),
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
        return {
            "mode": "bootstrap",
            "available_heads": [head["name"] for head in model_info.get("head_specs", [])],
            **model_info,
        }
    return {
        "mode": "trained",
        **model_info,
        "available_heads": [head["name"] for head in model_info.get("head_specs", [])],
    }
