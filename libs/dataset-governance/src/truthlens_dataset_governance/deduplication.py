from __future__ import annotations

from typing import Any

from truthlens_data_pipeline.paths import relative_path, repo_root, write_json, write_jsonl


def deduplicate_records(
    run_id: str,
    labeled_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen_source_urls: set[str] = set()
    seen_fingerprints: set[tuple[str, str]] = set()
    deduplicated: list[dict[str, Any]] = []
    duplicate_items: list[str] = []

    for record in labeled_records:
        key = (
            str(record["features"].get("text_fingerprint", "")),
            str(record["features"].get("image_fingerprint", "")),
        )
        source_url = str(record["source_url"])
        if source_url in seen_source_urls or key in seen_fingerprints:
            duplicate_items.append(record["item_id"])
            continue

        seen_source_urls.add(source_url)
        seen_fingerprints.add(key)
        deduplicated.append(record)

    deduplicated_path = repo_root() / "datasets" / "interim" / "deduplicated" / f"{run_id}.jsonl"
    write_jsonl(deduplicated_path, deduplicated)
    report = {
        "run_id": run_id,
        "raw_count": len(labeled_records),
        "deduplicated_count": len(deduplicated),
        "duplicate_count": len(duplicate_items),
        "duplicate_rate": round(len(duplicate_items) / max(len(labeled_records), 1), 4),
        "duplicate_items": duplicate_items,
        "deduplicated_path": relative_path(deduplicated_path),
        "strategy": "source_url_or_combined_text_image_fingerprint",
    }
    report_path = repo_root() / "datasets" / "manifests" / "audits" / f"{run_id}-deduplication.json"
    write_json(report_path, report)
    return deduplicated, report
