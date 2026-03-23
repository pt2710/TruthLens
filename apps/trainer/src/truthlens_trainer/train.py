from __future__ import annotations

import json
import pickle
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression

from truthlens_data_pipeline.paths import read_jsonl, repo_root
from truthlens_dataset_governance import load_latest_build_manifest
from truthlens_evaluation import compute_binary_metrics


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
                float(record["features"].get("thumbnail_saturation", 0.0)),
                float(record["features"].get("thumbnail_text_density", 0.0)),
                float(record["features"].get("mismatch_score", 0.0)),
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


def main() -> None:
    manifest = load_latest_build_manifest()
    train_records = _load_split_records(manifest, "train")
    validation_records = _load_split_records(manifest, "validation")
    test_records = _load_split_records(manifest, "test")

    train_labels = [_target(record) for record in train_records]
    validation_labels = [_target(record) for record in validation_records]
    test_labels = [_target(record) for record in test_records]

    text_vectorizer = CountVectorizer(ngram_range=(1, 2), min_df=1)
    train_text = text_vectorizer.fit_transform([record["title"] for record in train_records])
    validation_text = text_vectorizer.transform([record["title"] for record in validation_records])
    test_text = text_vectorizer.transform([record["title"] for record in test_records])

    text_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    text_model.fit(train_text, train_labels)

    vision_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    vision_model.fit(_vision_matrix(train_records), train_labels)

    metadata_model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    metadata_model.fit(_metadata_matrix(train_records), train_labels)

    validation_base_scores = np.column_stack(
        [
            text_model.predict_proba(validation_text)[:, 1],
            vision_model.predict_proba(_vision_matrix(validation_records))[:, 1],
            metadata_model.predict_proba(_metadata_matrix(validation_records))[:, 1],
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
    decision_threshold = _best_threshold(validation_labels, calibrated_validation_scores)

    test_base_scores = np.column_stack(
        [
            text_model.predict_proba(test_text)[:, 1],
            vision_model.predict_proba(_vision_matrix(test_records))[:, 1],
            metadata_model.predict_proba(_metadata_matrix(test_records))[:, 1],
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

    model_dir = repo_root() / "artifacts" / "trained_models" / "latest"
    model_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "text_vectorizer": text_vectorizer,
        "text_model": text_model,
        "vision_model": vision_model,
        "metadata_model": metadata_model,
        "fusion_model": fusion_model,
        "calibration_model": calibration_model,
    }
    with (model_dir / "model_bundle.pkl").open("wb") as handle:
        pickle.dump(bundle, handle)

    model_info = {
        "model_version": f"baseline-v1-{manifest['build_id']}",
        "trained_at": manifest["generated_at"],
        "build_id": manifest["build_id"],
        "decision_threshold": decision_threshold,
        "metrics": metrics,
    }
    (model_dir / "model_info.json").write_text(
        json.dumps(model_info, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    eval_dir = repo_root() / "artifacts" / "eval_runs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / f"{manifest['build_id']}.json").write_text(
        json.dumps(
            {
                "build_id": manifest["build_id"],
                "metrics": metrics,
                "sample_count": len(test_records),
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    print(model_info["model_version"])


if __name__ == "__main__":
    main()
