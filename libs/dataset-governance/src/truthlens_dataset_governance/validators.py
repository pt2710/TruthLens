from __future__ import annotations

from truthlens_shared_schemas.contracts import DatasetRecord

REQUIRED_GOVERNANCE_ARTIFACTS = [
    "source_manifest",
    "raw_acquisition_outputs",
    "interim_normalized_records",
    "deduplication_report",
    "split_manifest",
    "dataset_build_manifest",
    "dataset_card",
    "audit_report",
]


def validate_dataset_record(payload: dict) -> DatasetRecord:
    return DatasetRecord.model_validate(payload)


def verify_training_gate(artifacts: dict[str, bool]) -> tuple[bool, list[str]]:
    missing = [name for name in REQUIRED_GOVERNANCE_ARTIFACTS if not artifacts.get(name, False)]
    return (len(missing) == 0, missing)
