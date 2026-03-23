from __future__ import annotations

from typing import Any

from truthlens_data_pipeline import (
    PublicSourceSpec,
    acquire_discovered_items,
    normalize_acquired_items,
    persist_discovery_run,
    prepare_label_batches,
)
from truthlens_data_pipeline.paths import make_run_id
from truthlens_dataset_governance import (
    build_audit_report,
    build_processed_dataset,
    create_split_manifest,
    deduplicate_records,
)


def run_pipeline(
    run_id: str | None = None,
    build_id: str | None = None,
    public_sources: list[PublicSourceSpec] | None = None,
    fetcher: Any | None = None,
) -> dict[str, Any]:
    resolved_run_id = run_id or make_run_id("discovery")
    run_id, source_manifest, discovered_items = persist_discovery_run(
        resolved_run_id,
        public_sources=public_sources,
        fetcher=fetcher,
    )
    acquired_items, acquisition_manifest = acquire_discovered_items(run_id, discovered_items)
    normalized_records, transform_manifest = normalize_acquired_items(run_id, acquired_items)
    labeled_records, annotation_manifest = prepare_label_batches(run_id, normalized_records)
    deduplicated_records, deduplication_report = deduplicate_records(run_id, labeled_records)
    build_id = build_id or make_run_id("build")
    split_rows, split_manifest = create_split_manifest(build_id, deduplicated_records)
    build_manifest = build_processed_dataset(
        build_id=build_id,
        run_id=run_id,
        splits=split_rows,
        source_manifest=source_manifest.model_dump(),
        acquisition_manifest=acquisition_manifest,
        transform_manifest=transform_manifest,
        annotation_manifest=annotation_manifest,
        deduplication_report=deduplication_report,
        split_manifest=split_manifest,
    )
    audit_report = build_audit_report(build_id, split_rows, build_manifest, deduplication_report)
    return {
        "run_id": run_id,
        "build_id": build_id,
        "build_manifest": build_manifest,
        "audit_report": audit_report,
    }


def main() -> None:
    result = run_pipeline()
    print(result["build_manifest"]["dataset_build_manifest_path"])


if __name__ == "__main__":
    main()
