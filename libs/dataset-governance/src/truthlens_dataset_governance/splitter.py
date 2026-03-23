from __future__ import annotations

from typing import Any

from truthlens_data_pipeline.paths import relative_path, repo_root, write_json

SPLIT_CYCLE = ("validation", "test", "train", "train", "train")


def create_split_manifest(
    build_id: str,
    deduplicated_records: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    channel_names = sorted({record["channel_name"] for record in deduplicated_records})
    channel_to_split = {
        channel_name: SPLIT_CYCLE[index % len(SPLIT_CYCLE)]
        for index, channel_name in enumerate(channel_names)
    }

    splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    lineage_rows: list[dict[str, Any]] = []
    for record in deduplicated_records:
        split_name = channel_to_split[record["channel_name"]]
        record["provenance"]["split"] = split_name
        record["provenance"]["dataset_build_id"] = build_id
        splits[split_name].append(record)
        lineage_rows.append(
            {
                "item_id": record["item_id"],
                "channel_partition_key": record["channel_name"],
                "upload_window_key": str(record["metadata"].get("upload_time", ""))[:7],
                "template_cluster_key": record["features"].get("template_cluster", "unknown"),
                "discovery_batch_key": record["source_run_id"],
                "assigned_split": split_name,
            }
        )

    manifest = {
        "build_id": build_id,
        "strategy": "channel-first deterministic partitioning with explicit lineage keys",
        "partition_dimensions": [
            "channel_partition_key",
            "upload_window_key",
            "template_cluster_key",
            "discovery_batch_key",
        ],
        "channel_assignments": channel_to_split,
        "split_counts": {name: len(rows) for name, rows in splits.items()},
        "lineage_rows": lineage_rows,
    }
    split_manifest_path = repo_root() / "datasets" / "manifests" / "splits" / f"{build_id}.json"
    write_json(split_manifest_path, manifest)
    manifest["split_manifest_path"] = relative_path(split_manifest_path)
    return splits, manifest
