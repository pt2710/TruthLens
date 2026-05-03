from __future__ import annotations

import json
import pickle
import warnings
from typing import Any

import numpy as np
from sklearn import __version__ as sklearn_version
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
try:
    from torch import __version__ as torch_version
except ImportError:  # pragma: no cover - optional dependency
    torch_version = None

from truthlens_data_pipeline.paths import read_jsonl, repo_root, utc_now
from truthlens_dataset_governance import load_latest_build_manifest
from truthlens_evaluation import compute_binary_metrics, confusion_counts, expected_calibration_error
from truthlens_feature_extractors import (
    fallback_text_encoder_resolution,
    fallback_history_encoder_resolution,
    fallback_vision_encoder_resolution,
    history_encoder_resolution_payload,
    resolve_vision_encoder,
    resolve_history_encoder,
    resolve_text_encoder,
    sentence_transformer_matrix,
    thumbnail_array_batch,
    text_encoder_resolution_payload,
    vision_encoder_resolution_payload,
)
from truthlens_model_serving.registry import (
    ARCHITECTURE_PLAN_VERSION,
    HEAD_SPEC_VERSION,
    VISION_FEATURE_COUNT,
    VISION_FEATURE_VERSION,
    runtime_architecture_layers,
    runtime_head_specs,
)
from truthlens_model_serving.temporal import (
    temporal_artifacts_to_payload,
    temporal_available,
    temporal_history_scores_from_artifacts,
    train_temporal_history_encoder,
)
from truthlens_model_serving.vae import (
    artifacts_to_payload,
    packaging_anomaly_from_artifacts,
    train_packaging_vae,
    vae_available,
)
from truthlens_model_serving.vision import (
    thumbnail_scores_from_artifacts,
    train_vision_transformer_encoder,
    train_tiny_thumbnail_encoder,
    vision_artifacts_to_payload,
    vision_available,
    vision_transformer_available,
)


def _target(record: dict[str, Any]) -> int:
    return int(
        any(
            bool(record["labels"].get(name, False))
            for name in [
                "clickbait",
                "misleading_thumbnail",
                "misleading_title",
                "fearbait",
                "ai_mass_spam",
            ]
        )
    )


def _vision_matrix(records: list[dict[str, Any]]) -> np.ndarray:
    rows: list[list[float]] = []
    for record in records:
        rows.append(
            [
                float(record["features"].get("thumbnail_brightness", 0.0)),
                float(record["features"].get("thumbnail_saturation", 0.0)),
                float(record["features"].get("thumbnail_contrast", 0.0)),
                float(record["features"].get("thumbnail_text_density", 0.0)),
                float(record["features"].get("thumbnail_entropy", 0.0)),
                float(record["features"].get("thumbnail_aspect_ratio", 0.0)),
                float(record["features"].get("thumbnail_face_emphasis", 0.0)),
                float(record["features"].get("thumbnail_shock_indicator", 0.0)),
                float(record["features"].get("mismatch_score", 0.0)),
                float(record["features"].get("thumbnail_byte_size", 0.0)) / 100000.0,
                float(record["history"].get("prior_flags", 0.0)),
                float(record["metadata"].get("risk_seed", 0.0)),
            ]
        )
    return np.asarray(rows, dtype=float)


def _metadata_matrix(records: list[dict[str, Any]]) -> np.ndarray:
    rows: list[list[float]] = []
    for record in records:
        view_count = float(record["metadata"].get("view_count", 0.0))
        like_count = float(record["metadata"].get("like_count", 0.0))
        rows.append(
            [
                float(record["features"].get("title_length", 0.0)),
                float(record["features"].get("uppercase_ratio", 0.0)),
                float(record["features"].get("sensational_count", 0.0)),
                float(record["history"].get("prior_flags", 0.0)),
                float(record["history"]["channel_history_features"].get("channel_risk_mean", 0.0)),
                float(record["metadata"].get("duration_seconds", 0.0)),
                float(np.log1p(view_count)),
                like_count / max(view_count, 1.0),
                float(record["features"].get("transcript_mismatch_score", 0.0)),
            ]
        )
    return np.asarray(rows, dtype=float)


def _history_matrix(records: list[dict[str, Any]]) -> np.ndarray:
    rows: list[list[float]] = []
    for record in records:
        history = record["history"]["channel_history_features"]
        rows.append(
            [
                float(record["history"].get("prior_flags", 0.0)),
                float(history.get("channel_risk_mean", 0.0)),
                float(history.get("repeat_template_rate", 0.0)),
                float(history.get("recent_upload_velocity", history.get("publishing_velocity", 0.0))),
                float(history.get("engagement_anomaly", 1.0)),
            ]
        )
    return np.asarray(rows, dtype=float)


def _history_sequence_feature_row(record: dict[str, Any]) -> list[float]:
    metadata = record["metadata"]
    features = record["features"]
    history = record["history"]["channel_history_features"]
    view_count = float(metadata.get("view_count", 0.0))
    like_count = float(metadata.get("like_count", 0.0))
    return [
        float(metadata.get("risk_seed", 0.0)),
        float(features.get("transcript_mismatch_score", 0.0)),
        float(features.get("sensational_count", 0.0)),
        float(history.get("repeat_template_rate", 0.0)),
        float(history.get("recent_upload_velocity", history.get("publishing_velocity", 0.0))),
        float(history.get("engagement_anomaly", 1.0)),
        float(like_count / max(view_count, 1.0)),
    ]


def _history_sequence_tensor(
    records: list[dict[str, Any]],
    *,
    sequence_length: int,
) -> np.ndarray:
    channel_groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, record in enumerate(records):
        channel_groups.setdefault(record["channel_name"], []).append((index, record))
    sequences: list[np.ndarray | None] = [None] * len(records)
    for channel_records in channel_groups.values():
        ordered = sorted(channel_records, key=lambda item: str(item[1].get("collected_at", "")))
        feature_rows = [_history_sequence_feature_row(record) for _, record in ordered]
        feature_dim = len(feature_rows[0]) if feature_rows else 7
        zero_row = np.zeros(feature_dim, dtype=float)
        for position, (original_index, _) in enumerate(ordered):
            window = feature_rows[max(0, position - sequence_length + 1) : position + 1]
            padded_rows = [zero_row.copy() for _ in range(max(sequence_length - len(window), 0))]
            padded_rows.extend(np.asarray(row, dtype=float) for row in window)
            sequences[original_index] = np.asarray(padded_rows, dtype=float)
    default_sequence = np.zeros((sequence_length, 7), dtype=float)
    return np.asarray([sequence if sequence is not None else default_sequence for sequence in sequences], dtype=float)


def _packaging_matrix(records: list[dict[str, Any]]) -> np.ndarray:
    vision = _vision_matrix(records)
    metadata = _metadata_matrix(records)
    return np.column_stack(
        [
            vision[:, 0],
            vision[:, 1],
            vision[:, 2],
            vision[:, 3],
            vision[:, 4],
            vision[:, 5],
            vision[:, 6],
            vision[:, 7],
            vision[:, 8],
            vision[:, 9],
            vision[:, 10],
            vision[:, 11],
            metadata[:, 0],
            metadata[:, 1],
            metadata[:, 2],
            metadata[:, 4],
            metadata[:, 5],
            metadata[:, 6],
            metadata[:, 7],
            metadata[:, 8],
        ]
    ).astype(float)


def _thumbnail_image_batch(
    records: list[dict[str, Any]],
    *,
    image_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    thumbnail_paths = [repo_root() / str(record["thumbnail_path"]) for record in records]
    return thumbnail_array_batch(thumbnail_paths, image_size=image_size)


def _load_split_records(manifest: dict[str, Any], split_name: str) -> list[dict[str, Any]]:
    return read_jsonl(repo_root() / manifest["artifacts"][split_name])


def _fit_calibration(validation_scores: np.ndarray, validation_labels: list[int]) -> LogisticRegression | None:
    if len(set(validation_labels)) < 2:
        return None
    calibration_model = LogisticRegression(max_iter=400, random_state=42)
    calibration_model.fit(validation_scores.reshape(-1, 1), validation_labels)
    return calibration_model


def _best_threshold(labels: list[int], scores: np.ndarray) -> float:
    best_threshold = 0.5
    best_f1 = -1.0
    for threshold in [round(value / 100.0, 2) for value in range(25, 85, 5)]:
        metrics = compute_binary_metrics(labels, scores.tolist(), threshold=threshold)
        if float(metrics["f1"]) > best_f1:
            best_f1 = float(metrics["f1"])
            best_threshold = threshold
    return best_threshold


def _score_head_metrics(labels: list[int], scores: np.ndarray) -> dict[str, Any]:
    return {
        "metrics": compute_binary_metrics(labels, scores.tolist(), threshold=0.5),
        "calibration_error": expected_calibration_error(labels, scores.tolist()),
    }


def _checkpoint_iterations(max_iter: int) -> list[int]:
    checkpoints = [1, 2, 4, 8, 16, 32, 64, 128, 256, max_iter]
    normalized = sorted({value for value in checkpoints if 0 < value <= max_iter})
    if not normalized or normalized[-1] != max_iter:
        normalized.append(max_iter)
    return normalized


def _evaluate_checkpoint(
    model: LogisticRegression,
    fit_matrix: Any,
    fit_labels: list[int],
    eval_matrix: Any,
    eval_labels: list[int],
    *,
    fit_label: str,
    eval_label: str,
    iteration: int,
) -> dict[str, float | int]:
    fit_probabilities = model.predict_proba(fit_matrix)[:, 1]
    eval_probabilities = model.predict_proba(eval_matrix)[:, 1]
    return {
        "iteration": iteration,
        f"{fit_label}_loss": round(float(log_loss(fit_labels, fit_probabilities, labels=[0, 1])), 6),
        f"{eval_label}_loss": round(float(log_loss(eval_labels, eval_probabilities, labels=[0, 1])), 6),
        f"{fit_label}_accuracy": round(float(accuracy_score(fit_labels, fit_probabilities >= 0.5)), 6),
        f"{eval_label}_accuracy": round(float(accuracy_score(eval_labels, eval_probabilities >= 0.5)), 6),
    }


def _logistic_checkpoint_history(
    fit_matrix: Any,
    fit_labels: list[int],
    eval_matrix: Any,
    eval_labels: list[int],
    *,
    fit_label: str,
    eval_label: str,
    max_iter: int = 500,
) -> list[dict[str, float | int]]:
    history: list[dict[str, float | int]] = []
    for iteration in _checkpoint_iterations(max_iter):
        checkpoint_model = LogisticRegression(
            max_iter=iteration,
            random_state=42,
            class_weight="balanced",
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            checkpoint_model.fit(fit_matrix, fit_labels)
        history.append(
            _evaluate_checkpoint(
                checkpoint_model,
                fit_matrix,
                fit_labels,
                eval_matrix,
                eval_labels,
                fit_label=fit_label,
                eval_label=eval_label,
                iteration=iteration,
            )
        )
    return history


def _aggregate_histories(
    histories: dict[str, list[dict[str, float | int]]],
    *,
    fit_label: str,
    eval_label: str,
) -> list[dict[str, float | int]]:
    if not histories:
        return []
    ordered_names = sorted(histories)
    checkpoint_count = len(next(iter(histories.values())))
    aggregated: list[dict[str, float | int]] = []
    for index in range(checkpoint_count):
        checkpoints = [histories[name][index] for name in ordered_names]
        iteration = int(checkpoints[0]["iteration"])
        aggregated.append(
            {
                "iteration": iteration,
                f"{fit_label}_loss": round(
                    float(np.mean([float(checkpoint[f"{fit_label}_loss"]) for checkpoint in checkpoints])),
                    6,
                ),
                f"{eval_label}_loss": round(
                    float(np.mean([float(checkpoint[f"{eval_label}_loss"]) for checkpoint in checkpoints])),
                    6,
                ),
                f"{fit_label}_accuracy": round(
                    float(np.mean([float(checkpoint[f"{fit_label}_accuracy"]) for checkpoint in checkpoints])),
                    6,
                ),
                f"{eval_label}_accuracy": round(
                    float(np.mean([float(checkpoint[f"{eval_label}_accuracy"]) for checkpoint in checkpoints])),
                    6,
                ),
            }
        )
    return aggregated


def main() -> None:
    manifest = load_latest_build_manifest()
    training_generated_at = utc_now()
    train_records = _load_split_records(manifest, "train")
    validation_records = _load_split_records(manifest, "validation")
    test_records = _load_split_records(manifest, "test")

    train_labels = [_target(record) for record in train_records]
    validation_labels = [_target(record) for record in validation_records]
    test_labels = [_target(record) for record in test_records]

    text_encoder_resolution = resolve_text_encoder()
    text_vectorizer: CountVectorizer | None = None
    train_titles = [record["title"] for record in train_records]
    validation_titles = [record["title"] for record in validation_records]
    test_titles = [record["title"] for record in test_records]
    if text_encoder_resolution.actual_encoder == "sentence-transformer":
        try:
            model_name = text_encoder_resolution.sentence_transformer_model or ""
            train_text = sentence_transformer_matrix(train_titles, model_name)
            validation_text = sentence_transformer_matrix(validation_titles, model_name)
            test_text = sentence_transformer_matrix(test_titles, model_name)
        except Exception as error:
            text_encoder_resolution = fallback_text_encoder_resolution(
                text_encoder_resolution,
                reason=f"sentence-transformer path failed during training: {error}",
            )
            text_vectorizer = CountVectorizer(ngram_range=(1, 2), min_df=1)
            train_text = text_vectorizer.fit_transform(train_titles)
            validation_text = text_vectorizer.transform(validation_titles)
            test_text = text_vectorizer.transform(test_titles)
    else:
        text_vectorizer = CountVectorizer(ngram_range=(1, 2), min_df=1)
        train_text = text_vectorizer.fit_transform(train_titles)
        validation_text = text_vectorizer.transform(validation_titles)
        test_text = text_vectorizer.transform(test_titles)

    text_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    text_model.fit(train_text, train_labels)
    text_history = _logistic_checkpoint_history(
        train_text,
        train_labels,
        validation_text,
        validation_labels,
        fit_label="train",
        eval_label="validation",
        max_iter=500,
    )

    vision_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    vision_model.fit(_vision_matrix(train_records), train_labels)
    train_vision_matrix = _vision_matrix(train_records)
    validation_vision_matrix = _vision_matrix(validation_records)
    test_vision_matrix = _vision_matrix(test_records)
    vision_history = _logistic_checkpoint_history(
        train_vision_matrix,
        train_labels,
        validation_vision_matrix,
        validation_labels,
        fit_label="train",
        eval_label="validation",
        max_iter=500,
    )
    vision_encoder_resolution = resolve_vision_encoder()
    vision_encoder_artifacts = None
    validation_vision_scores = vision_model.predict_proba(validation_vision_matrix)[:, 1]
    test_vision_scores = vision_model.predict_proba(test_vision_matrix)[:, 1]
    if (
        vision_encoder_resolution.actual_encoder in {"tiny-cnn-thumbnail", "vision-transformer"}
        and vision_available()
    ):
        train_images, train_image_mask = _thumbnail_image_batch(
            train_records,
            image_size=vision_encoder_resolution.image_size,
        )
        validation_images, validation_image_mask = _thumbnail_image_batch(
            validation_records,
            image_size=vision_encoder_resolution.image_size,
        )
        test_images, test_image_mask = _thumbnail_image_batch(
            test_records,
            image_size=vision_encoder_resolution.image_size,
        )
        available_train_labels = [
            label
            for label, has_image in zip(train_labels, train_image_mask, strict=False)
            if bool(has_image)
        ]
        if int(train_image_mask.sum()) < 8 or len(set(available_train_labels)) < 2:
            vision_encoder_resolution = fallback_vision_encoder_resolution(
                vision_encoder_resolution,
                reason=(
                    "insufficient binary thumbnail coverage for the learned thumbnail encoder path"
                ),
                fallback_encoder=(
                    "tiny-cnn-thumbnail"
                    if vision_encoder_resolution.actual_encoder == "vision-transformer"
                    and vision_available()
                    else "vision-v2"
                ),
            )
        else:
            try:
                if (
                    vision_encoder_resolution.actual_encoder == "vision-transformer"
                    and vision_transformer_available()
                ):
                    trained_vision_encoder = train_vision_transformer_encoder(
                        train_images[train_image_mask],
                        available_train_labels,
                        patch_size=vision_encoder_resolution.patch_size,
                        transformer_hidden_size=vision_encoder_resolution.transformer_hidden_size,
                        transformer_num_hidden_layers=vision_encoder_resolution.transformer_num_hidden_layers,
                        transformer_num_attention_heads=vision_encoder_resolution.transformer_num_attention_heads,
                        transformer_intermediate_size=vision_encoder_resolution.transformer_intermediate_size,
                        hidden_dim=vision_encoder_resolution.hidden_dim,
                        pooling=vision_encoder_resolution.transformer_pooling,
                        epochs=vision_encoder_resolution.epochs,
                        learning_rate=vision_encoder_resolution.learning_rate,
                    )
                else:
                    trained_vision_encoder = train_tiny_thumbnail_encoder(
                        train_images[train_image_mask],
                        available_train_labels,
                        conv_channels=tuple(vision_encoder_resolution.conv_channels[:2]),
                        hidden_dim=vision_encoder_resolution.hidden_dim,
                        epochs=vision_encoder_resolution.epochs,
                        learning_rate=vision_encoder_resolution.learning_rate,
                    )
                vision_encoder_artifacts = vision_artifacts_to_payload(trained_vision_encoder)
                if bool(validation_image_mask.any()):
                    validation_vision_scores[validation_image_mask] = thumbnail_scores_from_artifacts(
                        validation_images[validation_image_mask],
                        trained_vision_encoder,
                    )
                if bool(test_image_mask.any()):
                    test_vision_scores[test_image_mask] = thumbnail_scores_from_artifacts(
                        test_images[test_image_mask],
                        trained_vision_encoder,
                    )
            except Exception as error:
                if (
                    vision_encoder_resolution.actual_encoder == "vision-transformer"
                    and vision_available()
                ):
                    fallback_resolution = fallback_vision_encoder_resolution(
                        vision_encoder_resolution,
                        reason=f"vision transformer path failed during training: {error}",
                        fallback_encoder="tiny-cnn-thumbnail",
                    )
                    try:
                        trained_vision_encoder = train_tiny_thumbnail_encoder(
                            train_images[train_image_mask],
                            available_train_labels,
                            conv_channels=tuple(fallback_resolution.conv_channels[:2]),
                            hidden_dim=fallback_resolution.hidden_dim,
                            epochs=fallback_resolution.epochs,
                            learning_rate=fallback_resolution.learning_rate,
                        )
                        vision_encoder_resolution = fallback_resolution
                        vision_encoder_artifacts = vision_artifacts_to_payload(trained_vision_encoder)
                        if bool(validation_image_mask.any()):
                            validation_vision_scores[validation_image_mask] = thumbnail_scores_from_artifacts(
                                validation_images[validation_image_mask],
                                trained_vision_encoder,
                            )
                        if bool(test_image_mask.any()):
                            test_vision_scores[test_image_mask] = thumbnail_scores_from_artifacts(
                                test_images[test_image_mask],
                                trained_vision_encoder,
                            )
                    except Exception as fallback_error:
                        vision_encoder_resolution = fallback_vision_encoder_resolution(
                            fallback_resolution,
                            reason=(
                                "vision transformer training failed and the tiny CNN fallback also failed: "
                                f"{fallback_error}"
                            ),
                            fallback_encoder="vision-v2",
                        )
                else:
                    vision_encoder_resolution = fallback_vision_encoder_resolution(
                        vision_encoder_resolution,
                        reason=f"tiny CNN vision path failed during training: {error}",
                        fallback_encoder="vision-v2",
                    )

    metadata_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    train_metadata_matrix = _metadata_matrix(train_records)
    validation_metadata_matrix = _metadata_matrix(validation_records)
    test_metadata_matrix = _metadata_matrix(test_records)
    metadata_model.fit(train_metadata_matrix, train_labels)
    metadata_history = _logistic_checkpoint_history(
        train_metadata_matrix,
        train_labels,
        validation_metadata_matrix,
        validation_labels,
        fit_label="train",
        eval_label="validation",
        max_iter=500,
    )

    history_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    train_history_matrix = _history_matrix(train_records)
    validation_history_matrix = _history_matrix(validation_records)
    test_history_matrix = _history_matrix(test_records)
    history_model.fit(train_history_matrix, train_labels)
    baseline_history_head_history = _logistic_checkpoint_history(
        train_history_matrix,
        train_labels,
        validation_history_matrix,
        validation_labels,
        fit_label="train",
        eval_label="validation",
        max_iter=500,
    )
    history_encoder_resolution = resolve_history_encoder()
    history_sequence_artifacts = None
    train_history_sequences = _history_sequence_tensor(
        train_records,
        sequence_length=history_encoder_resolution.sequence_length,
    )
    validation_history_sequences = _history_sequence_tensor(
        validation_records,
        sequence_length=history_encoder_resolution.sequence_length,
    )
    test_history_sequences = _history_sequence_tensor(
        test_records,
        sequence_length=history_encoder_resolution.sequence_length,
    )
    validation_history_scores = history_model.predict_proba(validation_history_matrix)[:, 1]
    test_history_scores = history_model.predict_proba(test_history_matrix)[:, 1]
    if history_encoder_resolution.actual_encoder == "lstm-sequence" and temporal_available():
        try:
            temporal_history = train_temporal_history_encoder(
                train_history_sequences,
                train_labels,
                hidden_dim=history_encoder_resolution.hidden_dim,
                num_layers=history_encoder_resolution.num_layers,
                epochs=history_encoder_resolution.epochs,
                learning_rate=history_encoder_resolution.learning_rate,
            )
            history_sequence_artifacts = temporal_artifacts_to_payload(temporal_history)
            validation_history_scores = temporal_history_scores_from_artifacts(
                validation_history_sequences,
                temporal_history,
            )
            test_history_scores = temporal_history_scores_from_artifacts(
                test_history_sequences,
                temporal_history,
            )
        except Exception as error:
            history_encoder_resolution = fallback_history_encoder_resolution(
                history_encoder_resolution,
                reason=f"lstm history path failed during training: {error}",
            )

    packaging_vae_artifacts = None
    validation_anomaly_scores = np.zeros(len(validation_records), dtype=float)
    test_anomaly_scores = np.zeros(len(test_records), dtype=float)
    if vae_available():
        anomaly_train_records = [
            record for record, label in zip(train_records, train_labels, strict=False) if label == 0
        ]
        anomaly_source_records = anomaly_train_records or train_records
        packaging_vae = train_packaging_vae(_packaging_matrix(anomaly_source_records))
        packaging_vae_artifacts = artifacts_to_payload(packaging_vae)
        validation_anomaly_scores, _ = packaging_anomaly_from_artifacts(
            _packaging_matrix(validation_records),
            packaging_vae,
        )
        test_anomaly_scores, _ = packaging_anomaly_from_artifacts(
            _packaging_matrix(test_records),
            packaging_vae,
        )

    validation_base_scores = np.column_stack(
        [
            text_model.predict_proba(validation_text)[:, 1],
            validation_vision_scores,
            metadata_model.predict_proba(validation_metadata_matrix)[:, 1],
            validation_history_scores,
            validation_anomaly_scores,
        ]
    )
    fusion_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    fusion_model.fit(validation_base_scores, validation_labels)
    validation_fusion_scores = fusion_model.predict_proba(validation_base_scores)[:, 1]
    calibration_model = _fit_calibration(validation_fusion_scores, validation_labels)
    calibrated_validation_scores = (
        calibration_model.predict_proba(validation_fusion_scores.reshape(-1, 1))[:, 1]
        if calibration_model is not None
        else validation_fusion_scores
    )
    validation_metrics = compute_binary_metrics(
        validation_labels,
        calibrated_validation_scores.tolist(),
        threshold=0.5,
    )
    validation_calibration_error = expected_calibration_error(
        validation_labels,
        calibrated_validation_scores.tolist(),
    )
    decision_threshold = _best_threshold(validation_labels, calibrated_validation_scores)

    test_text_scores = text_model.predict_proba(test_text)[:, 1]
    test_metadata_scores = metadata_model.predict_proba(test_metadata_matrix)[:, 1]
    test_base_scores = np.column_stack(
        [
            test_text_scores,
            test_vision_scores,
            test_metadata_scores,
            test_history_scores,
            test_anomaly_scores,
        ]
    )
    test_fusion_scores = fusion_model.predict_proba(test_base_scores)[:, 1]
    fusion_history = _logistic_checkpoint_history(
        validation_base_scores,
        validation_labels,
        test_base_scores,
        test_labels,
        fit_label="validation",
        eval_label="test",
        max_iter=500,
    )
    calibrated_test_scores = (
        calibration_model.predict_proba(test_fusion_scores.reshape(-1, 1))[:, 1]
        if calibration_model is not None
        else test_fusion_scores
    )
    metrics = compute_binary_metrics(
        test_labels,
        calibrated_test_scores.tolist(),
        threshold=decision_threshold,
    )
    calibration_error = expected_calibration_error(test_labels, calibrated_test_scores.tolist())
    confusion = confusion_counts(test_labels, calibrated_test_scores.tolist(), threshold=decision_threshold)
    per_head_metrics = {
        "text": _score_head_metrics(test_labels, test_text_scores),
        "vision": _score_head_metrics(test_labels, test_vision_scores),
        "metadata": _score_head_metrics(test_labels, test_metadata_scores),
        "history": _score_head_metrics(test_labels, test_history_scores),
        "anomaly": _score_head_metrics(test_labels, test_anomaly_scores),
        "fusion": _score_head_metrics(test_labels, test_fusion_scores),
        "calibrated": _score_head_metrics(test_labels, calibrated_test_scores),
    }

    model_dir = repo_root() / "artifacts" / "trained_models" / "latest"
    model_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "text_model": text_model,
        "vision_model": vision_model,
        "metadata_model": metadata_model,
        "history_model": history_model,
        "fusion_model": fusion_model,
        "calibration_model": calibration_model,
        "text_encoder_resolution": text_encoder_resolution_payload(text_encoder_resolution),
        "vision_encoder_resolution": vision_encoder_resolution_payload(vision_encoder_resolution),
        "history_encoder_resolution": history_encoder_resolution_payload(history_encoder_resolution),
    }
    if text_vectorizer is not None:
        bundle["text_vectorizer"] = text_vectorizer
    if vision_encoder_artifacts is not None:
        bundle["vision_encoder_artifacts"] = vision_encoder_artifacts
    if history_sequence_artifacts is not None:
        bundle["history_sequence_artifacts"] = history_sequence_artifacts
    if packaging_vae_artifacts is not None:
        bundle["packaging_vae_artifacts"] = packaging_vae_artifacts
    with (model_dir / "model_bundle.pkl").open("wb") as handle:
        pickle.dump(bundle, handle)

    model_info = {
        "model_version": f"baseline-v1-{manifest['build_id']}",
        "trained_at": training_generated_at,
        "build_id": manifest["build_id"],
        "head_spec_version": HEAD_SPEC_VERSION,
        "head_specs": runtime_head_specs(
            text_encoder_override=text_encoder_resolution.actual_encoder,
            vision_encoder_override=vision_encoder_resolution.actual_encoder,
            history_encoder_override=history_encoder_resolution.actual_encoder,
        ),
        "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
        "architecture_layers": runtime_architecture_layers(),
        "text_encoder_resolution": text_encoder_resolution_payload(text_encoder_resolution),
        "vision_encoder_resolution": vision_encoder_resolution_payload(vision_encoder_resolution),
        "history_encoder_resolution": history_encoder_resolution_payload(history_encoder_resolution),
        "training_library_versions": {
            "scikit_learn": sklearn_version,
        },
        "vision_feature_version": VISION_FEATURE_VERSION,
        "vision_feature_count": VISION_FEATURE_COUNT,
        "fusion_profile": {
            "strategy": "logistic-fusion",
            "head_weights": {
                "text": round(float(fusion_model.coef_[0][0]), 4),
                "vision": round(float(fusion_model.coef_[0][1]), 4),
                "metadata": round(float(fusion_model.coef_[0][2]), 4),
                "history": round(float(fusion_model.coef_[0][3]), 4),
                "anomaly": round(float(fusion_model.coef_[0][4]), 4),
            },
            "intercept": round(float(fusion_model.intercept_[0]), 4),
        },
        "decision_threshold": decision_threshold,
        "metrics": metrics,
        "calibration_error": calibration_error,
        "confusion_matrix": confusion,
        "validation_metrics": validation_metrics,
        "validation_calibration_error": validation_calibration_error,
        "per_head_metrics": per_head_metrics,
    }
    if torch_version is not None:
        model_info["training_library_versions"]["torch"] = str(torch_version)
    (model_dir / "model_info.json").write_text(
        json.dumps(model_info, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    eval_dir = repo_root() / "artifacts" / "eval_runs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    evaluation_payload = {
        "build_id": manifest["build_id"],
        "generated_at": training_generated_at,
        "metrics": metrics,
        "calibration_error": calibration_error,
        "confusion_matrix": confusion,
        "validation_metrics": validation_metrics,
        "validation_calibration_error": validation_calibration_error,
        "per_head_metrics": per_head_metrics,
        "sample_count": len(test_records),
    }
    (eval_dir / f"{manifest['build_id']}.json").write_text(
        json.dumps(evaluation_payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    training_history_payload = {
        "build_id": manifest["build_id"],
        "generated_at": training_generated_at,
        "baseline_heads": {
            "fit_label": "train",
            "eval_label": "validation",
            "heads": {
                "text": text_history,
                "vision": vision_history,
                "metadata": metadata_history,
                "history": baseline_history_head_history,
            },
            "aggregated": _aggregate_histories(
                {
                    "text": text_history,
                    "vision": vision_history,
                    "metadata": metadata_history,
                    "history": baseline_history_head_history,
                },
                fit_label="train",
                eval_label="validation",
            ),
        },
        "fusion": {
            "fit_label": "validation",
            "eval_label": "test",
            "history": fusion_history,
        },
    }
    (eval_dir / f"{manifest['build_id']}-training-history.json").write_text(
        json.dumps(training_history_payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    reports_dir = repo_root() / "artifacts" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{manifest['build_id']}-model-eval.json").write_text(
        json.dumps(evaluation_payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(model_info["model_version"])


if __name__ == "__main__":
    main()
