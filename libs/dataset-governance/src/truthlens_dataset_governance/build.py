from __future__ import annotations

from collections import Counter
from typing import Any

from truthlens_data_pipeline.paths import (
    ensure_dir,
    read_json,
    relative_path,
    repo_root,
    utc_now,
    write_json,
    write_jsonl,
)


def _dataset_card(build_id: str, splits: dict[str, list[dict[str, Any]]]) -> str:
    total = sum(len(rows) for rows in splits.values())
    flagged = sum(
        1
        for rows in splits.values()
        for record in rows
        if any(
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
    content_class_counts: Counter[str] = Counter()
    dominant_bias_counts: Counter[str] = Counter()
    for rows in splits.values():
        for record in rows:
            content_class_counts[str(record["features"].get("content_class", "unknown"))] += 1
            dominant_bias_counts[str(record["features"].get("dominant_bias_risk", "balanced-context"))] += 1
    class_lines = [
        f"  - {content_class}: {count}"
        for content_class, count in sorted(content_class_counts.items())
    ] or ["  - unknown: 0"]
    bias_lines = [
        f"  - {bias_name}: {count}"
        for bias_name, count in sorted(dominant_bias_counts.items())
    ] or ["  - balanced-context: 0"]
    return "\n".join(
        [
            f"# TruthLens Dataset Card: {build_id}",
            "",
            f"- Generated at: {utc_now()}",
            f"- Total records: {total}",
            f"- Train records: {len(splits['train'])}",
            f"- Validation records: {len(splits['validation'])}",
            f"- Test records: {len(splits['test'])}",
            f"- Weakly flagged records: {flagged}",
            "- Split strategy: channel-first deterministic partitioning with explicit lineage keys.",
            "- Governance gates: schema validation, duplicate rate, channel leakage, provenance completeness.",
            "- Content-class coverage:",
            *class_lines,
            "- Dominant bias-risk coverage:",
            *bias_lines,
        ]
    )


def build_processed_dataset(
    build_id: str,
    run_id: str,
    splits: dict[str, list[dict[str, Any]]],
    source_manifest: dict[str, Any],
    acquisition_manifest: dict[str, Any],
    transform_manifest: dict[str, Any],
    annotation_manifest: dict[str, Any],
    deduplication_report: dict[str, Any],
    split_manifest: dict[str, Any],
    operator_feedback_manifest: dict[str, Any] | None = None,
    operator_ingestion_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = repo_root()
    split_paths: dict[str, str] = {}
    for split_name, rows in splits.items():
        split_path = root / "datasets" / "processed" / split_name / f"{build_id}.jsonl"
        latest_path = root / "datasets" / "processed" / split_name / "latest.jsonl"
        write_jsonl(split_path, rows)
        write_jsonl(latest_path, rows)
        split_paths[split_name] = relative_path(split_path)

    gold_rows = [
        record
        for split_name in ("validation", "test")
        for record in splits[split_name][:2]
        if record["labels"].get("review_required", False)
    ]
    gold_path = root / "datasets" / "labels" / "gold" / f"{build_id}.jsonl"
    write_jsonl(gold_path, gold_rows)
    adjudication_path = root / "datasets" / "labels" / "adjudication" / f"{build_id}.json"
    write_json(
        adjudication_path,
        {
            "build_id": build_id,
            "run_id": run_id,
            "generated_at": utc_now(),
            "gold_count": len(gold_rows),
            "adjudicated_count": 0,
            "unresolved_count": len(gold_rows),
            "pending_items": [
                {
                    "item_id": record["item_id"],
                    "title": record["title"],
                    "channel_name": record["channel_name"],
                    "content_class": str(record["features"].get("content_class", "unknown")),
                    "content_class_confidence": float(
                        record["features"].get("content_class_confidence", 0.0)
                    ),
                    "dominant_bias_risk": str(
                        record["features"].get("dominant_bias_risk", "balanced-context")
                    ),
                    "labels": dict(record.get("labels", {})),
                    "annotator_notes": list(record.get("annotator_notes", [])),
                }
                for record in gold_rows
            ],
            "adjudications": [],
            "source_gold_path": relative_path(gold_path),
        },
    )

    dataset_card_dir = ensure_dir(root / "datasets" / "dataset_cards")
    dataset_card_path = dataset_card_dir / f"{build_id}.md"
    dataset_card_path.write_text(_dataset_card(build_id, splits), encoding="utf-8")
    latest_card_path = dataset_card_dir / "latest.md"
    latest_card_path.write_text(dataset_card_path.read_text(encoding="utf-8"), encoding="utf-8")

    build_manifest = {
        "build_id": build_id,
        "run_id": run_id,
        "generated_at": utc_now(),
        "sources": {
            "source_manifest": source_manifest,
            "raw_acquisition_outputs": acquisition_manifest,
            "transform_manifest": transform_manifest,
            "annotation_manifest": annotation_manifest,
            "deduplication_report": deduplication_report,
            "split_manifest": split_manifest,
            "operator_feedback_manifest": operator_feedback_manifest or {},
            "operator_ingestion_manifest": operator_ingestion_manifest or {},
        },
        "artifacts": {
            "train": split_paths["train"],
            "validation": split_paths["validation"],
            "test": split_paths["test"],
            "gold": relative_path(gold_path),
            "adjudication": relative_path(adjudication_path),
            "dataset_card": relative_path(dataset_card_path),
        },
        "counts": {name: len(rows) for name, rows in splits.items()},
        "class_coverage": {
            content_class: sum(
                1
                for rows in splits.values()
                for record in rows
                if str(record["features"].get("content_class", "unknown")) == content_class
            )
            for content_class in sorted(
                {
                    str(record["features"].get("content_class", "unknown"))
                    for rows in splits.values()
                    for record in rows
                }
            )
        },
        "operator_feedback": {
            "candidate_count": int((operator_feedback_manifest or {}).get("summary", {}).get("candidate_count", 0)),
            "confirmed_count": int((operator_feedback_manifest or {}).get("summary", {}).get("confirmed_count", 0)),
            "ingested_count": int((operator_ingestion_manifest or {}).get("ingested_count", 0)),
            "source_manifest_path": (operator_ingestion_manifest or {}).get("source_manifest_path")
            or (operator_feedback_manifest or {}).get("source_manifest_path"),
            "source_gold_path": (operator_ingestion_manifest or {}).get("source_gold_path"),
        },
    }
    build_manifest_path = root / "datasets" / "manifests" / "builds" / f"{build_id}.json"
    latest_manifest_path = root / "datasets" / "manifests" / "builds" / "latest.json"
    write_json(build_manifest_path, build_manifest)
    write_json(latest_manifest_path, build_manifest)
    build_manifest["dataset_build_manifest_path"] = relative_path(build_manifest_path)
    return build_manifest


def load_latest_build_manifest() -> dict[str, Any]:
    latest_manifest_path = repo_root() / "datasets" / "manifests" / "builds" / "latest.json"
    return read_json(latest_manifest_path)
