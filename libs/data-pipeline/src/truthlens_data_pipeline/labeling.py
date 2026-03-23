from __future__ import annotations

from typing import Any

from truthlens_data_pipeline.paths import relative_path, repo_root, write_json, write_jsonl


def _combine_label_score(record: dict[str, Any]) -> float:
    metadata = record["metadata"]
    features = record["features"]
    history = record["history"]["channel_history_features"]
    score = (
        float(metadata.get("risk_seed", 0.0)) * 0.45
        + float(features.get("sensational_count", 0.0)) * 0.12
        + float(features.get("mismatch_score", 0.0)) * 0.18
        + float(record["history"].get("prior_flags", 0.0)) * 0.03
        + float(history.get("channel_risk_mean", 0.0)) * 0.18
    )
    return round(min(score, 0.99), 4)


def prepare_label_batches(
    run_id: str,
    normalized_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    labeled_records: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    hard_negative_queue: list[dict[str, Any]] = []
    disagreement_queue: list[dict[str, Any]] = []

    for record in normalized_records:
        weak_label_score = _combine_label_score(record)
        clickbait = bool(record["features"].get("sensational_count", 0) > 0)
        misleading_thumbnail = bool(record["metadata"].get("risk_seed", 0.0) > 0.7)
        misleading_title = bool(record["features"].get("mismatch_score", 0.0) > 0.58)
        fearbait = bool(weak_label_score > 0.62)
        ai_mass_spam = bool(record["history"].get("prior_flags", 0) >= 3 and clickbait)
        review_required = 0.35 <= weak_label_score <= 0.8 or ai_mass_spam

        record["labels"] = {
            "clickbait": clickbait,
            "misleading_thumbnail": misleading_thumbnail,
            "misleading_title": misleading_title,
            "fearbait": fearbait,
            "ai_mass_spam": ai_mass_spam,
            "review_required": review_required,
        }
        record["metadata"]["weak_label_score"] = weak_label_score
        record["metadata"]["uncertainty_bucket"] = (
            "high" if review_required else "low" if weak_label_score < 0.3 else "medium"
        )
        record["metadata"]["source_trust_flag"] = (
            "elevated-risk" if record["history"].get("prior_flags", 0) > 1 else "baseline"
        )

        note = (
            f"Weak label score={weak_label_score} template={record['features'].get('template_cluster', 'unknown')}"
        )
        record["annotator_notes"] = [note]
        labeled_records.append(record)

        if review_required:
            review_queue.append(
                {
                    "item_id": record["item_id"],
                    "title": record["title"],
                    "weak_label_score": weak_label_score,
                    "uncertainty_bucket": record["metadata"]["uncertainty_bucket"],
                }
            )
        elif weak_label_score < 0.24:
            hard_negative_queue.append({"item_id": record["item_id"], "title": record["title"]})

        if clickbait and not misleading_title:
            disagreement_queue.append({"item_id": record["item_id"], "title": record["title"]})

    root = repo_root()
    weak_labels_path = root / "datasets" / "labels" / "weak_labels" / f"{run_id}.jsonl"
    annotation_batch_path = root / "datasets" / "labels" / "annotation_batches" / f"{run_id}.json"
    write_jsonl(weak_labels_path, labeled_records)
    write_json(
        annotation_batch_path,
        {
            "run_id": run_id,
            "review_queue": review_queue,
            "hard_negative_queue": hard_negative_queue,
            "disagreement_queue": disagreement_queue,
            "annotator_notes_fields": ["weak_label_score", "uncertainty_bucket", "source_trust_flag"],
        },
    )
    annotation_manifest = {
        "run_id": run_id,
        "generated_at": normalized_records[0]["collected_at"] if normalized_records else "",
        "annotation_batch_path": relative_path(annotation_batch_path),
        "weak_labels_path": relative_path(weak_labels_path),
        "review_count": len(review_queue),
        "hard_negative_count": len(hard_negative_queue),
        "disagreement_count": len(disagreement_queue),
    }
    annotation_manifest_path = root / "datasets" / "manifests" / "builds" / f"{run_id}-annotation.json"
    write_json(annotation_manifest_path, annotation_manifest)
    return labeled_records, annotation_manifest
