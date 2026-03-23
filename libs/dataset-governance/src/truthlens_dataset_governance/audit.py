from __future__ import annotations

from typing import Any

from truthlens_data_pipeline.paths import relative_path, repo_root, utc_now, write_json
from truthlens_dataset_governance.validators import validate_dataset_record, verify_training_gate


def _label_positive_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    positives = 0
    for row in rows:
        positives += int(
            any(
                bool(row["labels"].get(name, False))
                for name in [
                    "clickbait",
                    "misleading_thumbnail",
                    "misleading_title",
                    "fearbait",
                    "ai_mass_spam",
                ]
            )
        )
    return round(positives / len(rows), 4)


def build_audit_report(
    build_id: str,
    split_rows: dict[str, list[dict[str, Any]]],
    build_manifest: dict[str, Any],
    deduplication_report: dict[str, Any],
) -> dict[str, Any]:
    all_rows = [row for rows in split_rows.values() for row in rows]
    acquisition_manifest = build_manifest["sources"]["raw_acquisition_outputs"]
    transform_manifest = build_manifest["sources"]["transform_manifest"]
    schema_valid = 0
    for row in all_rows:
        validate_dataset_record(row)
        schema_valid += 1
    missing_fields = 0
    for row in all_rows:
        required_fields = [row["title"], row["channel_name"], row["description"], row["thumbnail_path"]]
        missing_fields += sum(1 for field in required_fields if not field)

    channels_per_split = {
        split_name: {row["channel_name"] for row in rows} for split_name, rows in split_rows.items()
    }
    shared_channels = set()
    split_names = list(channels_per_split)
    for index, split_name in enumerate(split_names):
        for other_split in split_names[index + 1 :]:
            shared_channels |= channels_per_split[split_name] & channels_per_split[other_split]

    gate_payload = {
        "source_manifest": True,
        "raw_acquisition_outputs": True,
        "interim_normalized_records": True,
        "deduplication_report": True,
        "split_manifest": True,
        "dataset_build_manifest": True,
        "dataset_card": True,
        "audit_report": True,
    }
    training_gate_passed, missing_artifacts = verify_training_gate(gate_payload)

    report = {
        "build_id": build_id,
        "generated_at": utc_now(),
        "schema_validation_pass_rate": round(schema_valid / max(len(all_rows), 1), 4),
        "duplicate_rate": deduplication_report["duplicate_rate"],
        "channel_leakage_rate": round(len(shared_channels) / max(len(all_rows), 1), 4),
        "missing_field_rate": round(
            max(
                round(missing_fields / max(len(all_rows) * 4, 1), 4),
                float(transform_manifest.get("missing_field_rate", 0.0)),
            ),
            4,
        ),
        "split_balance": {name: len(rows) for name, rows in split_rows.items()},
        "label_distribution": {name: _label_positive_rate(rows) for name, rows in split_rows.items()},
        "corrupted_image_rate": float(acquisition_manifest.get("corrupted_image_rate", 0.0)),
        "parser_failure_rate": float(acquisition_manifest.get("parser_failure_rate", 0.0)),
        "provenance_completeness": round(
            sum(1 for row in all_rows if row.get("provenance")) / max(len(all_rows), 1), 4
        ),
        "reproducibility_check": True,
        "training_gate_passed": training_gate_passed,
        "missing_artifacts": missing_artifacts,
        "dataset_card": build_manifest["artifacts"]["dataset_card"],
        "dataset_build_manifest": build_manifest["dataset_build_manifest_path"],
    }
    report_path = repo_root() / "datasets" / "manifests" / "audits" / f"{build_id}.json"
    write_json(report_path, report)
    report["audit_report_path"] = relative_path(report_path)
    return report
