from __future__ import annotations

import json
import pickle
from typing import Any

import numpy as np
from sklearn import __version__ as sklearn_version
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression

from truthlens_data_pipeline.paths import read_jsonl, repo_root
from truthlens_dataset_governance import load_latest_build_manifest
from truthlens_evaluation import compute_binary_metrics, confusion_counts, expected_calibration_error
from truthlens_feature_extractors import (
    fallback_text_encoder_resolution,
    resolve_text_encoder,
    sentence_transformer_matrix,
    text_encoder_resolution_payload,
)
from truthlens_model_serving.registry import (
    ARCHITECTURE_PLAN_VERSION,
    HEAD_SPEC_VERSION,
    VISION_FEATURE_COUNT,
    VISION_FEATURE_VERSION,
    runtime_architecture_layers,
    runtime_head_specs,
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


def main() -> None:
    manifest = load_latest_build_manifest()
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

    vision_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    vision_model.fit(_vision_matrix(train_records), train_labels)

    metadata_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    metadata_model.fit(_metadata_matrix(train_records), train_labels)

    history_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    history_model.fit(_history_matrix(train_records), train_labels)

    validation_base_scores = np.column_stack(
        [
            text_model.predict_proba(validation_text)[:, 1],
            vision_model.predict_proba(_vision_matrix(validation_records))[:, 1],
            metadata_model.predict_proba(_metadata_matrix(validation_records))[:, 1],
            history_model.predict_proba(_history_matrix(validation_records))[:, 1],
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
    test_vision_scores = vision_model.predict_proba(_vision_matrix(test_records))[:, 1]
    test_metadata_scores = metadata_model.predict_proba(_metadata_matrix(test_records))[:, 1]
    test_history_scores = history_model.predict_proba(_history_matrix(test_records))[:, 1]
    test_base_scores = np.column_stack(
        [
            test_text_scores,
            test_vision_scores,
            test_metadata_scores,
            test_history_scores,
        ]
    )
    test_fusion_scores = fusion_model.predict_proba(test_base_scores)[:, 1]
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
    }
    if text_vectorizer is not None:
        bundle["text_vectorizer"] = text_vectorizer
    with (model_dir / "model_bundle.pkl").open("wb") as handle:
        pickle.dump(bundle, handle)

    model_info = {
        "model_version": f"baseline-v1-{manifest['build_id']}",
        "trained_at": manifest["generated_at"],
        "build_id": manifest["build_id"],
        "head_spec_version": HEAD_SPEC_VERSION,
        "head_specs": runtime_head_specs(text_encoder_override=text_encoder_resolution.actual_encoder),
        "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
        "architecture_layers": runtime_architecture_layers(),
        "text_encoder_resolution": text_encoder_resolution_payload(text_encoder_resolution),
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
    (model_dir / "model_info.json").write_text(
        json.dumps(model_info, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    eval_dir = repo_root() / "artifacts" / "eval_runs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    evaluation_payload = {
        "build_id": manifest["build_id"],
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
    reports_dir = repo_root() / "artifacts" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{manifest['build_id']}-model-eval.json").write_text(
        json.dumps(evaluation_payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(model_info["model_version"])


if __name__ == "__main__":
    main()
