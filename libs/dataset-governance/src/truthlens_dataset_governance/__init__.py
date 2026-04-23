from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .audit import build_audit_report
    from .build import build_processed_dataset, load_latest_build_manifest
    from .deduplication import deduplicate_records
    from .intake import (
        build_supplemental_candidate_batch,
        supplemental_adjudication_path,
        supplemental_gold_path,
    )
    from .operator_feedback import (
        ingest_operator_feedback_records,
        load_latest_operator_feedback_manifest,
        materialize_operator_feedback_artifacts,
        operator_adjudication_path,
        operator_gold_path,
    )
    from .splitter import create_split_manifest
    from .validators import REQUIRED_GOVERNANCE_ARTIFACTS, validate_dataset_record, verify_training_gate

_EXPORTS = {
    "REQUIRED_GOVERNANCE_ARTIFACTS": (".validators", "REQUIRED_GOVERNANCE_ARTIFACTS"),
    "build_audit_report": (".audit", "build_audit_report"),
    "build_processed_dataset": (".build", "build_processed_dataset"),
    "build_supplemental_candidate_batch": (".intake", "build_supplemental_candidate_batch"),
    "create_split_manifest": (".splitter", "create_split_manifest"),
    "deduplicate_records": (".deduplication", "deduplicate_records"),
    "ingest_operator_feedback_records": (".operator_feedback", "ingest_operator_feedback_records"),
    "load_latest_build_manifest": (".build", "load_latest_build_manifest"),
    "load_latest_operator_feedback_manifest": (".operator_feedback", "load_latest_operator_feedback_manifest"),
    "materialize_operator_feedback_artifacts": (".operator_feedback", "materialize_operator_feedback_artifacts"),
    "operator_adjudication_path": (".operator_feedback", "operator_adjudication_path"),
    "operator_gold_path": (".operator_feedback", "operator_gold_path"),
    "supplemental_adjudication_path": (".intake", "supplemental_adjudication_path"),
    "supplemental_gold_path": (".intake", "supplemental_gold_path"),
    "validate_dataset_record": (".validators", "validate_dataset_record"),
    "verify_training_gate": (".validators", "verify_training_gate"),
}

__all__ = [
    "REQUIRED_GOVERNANCE_ARTIFACTS",
    "build_audit_report",
    "build_processed_dataset",
    "build_supplemental_candidate_batch",
    "create_split_manifest",
    "deduplicate_records",
    "ingest_operator_feedback_records",
    "load_latest_build_manifest",
    "load_latest_operator_feedback_manifest",
    "materialize_operator_feedback_artifacts",
    "operator_adjudication_path",
    "operator_gold_path",
    "supplemental_adjudication_path",
    "supplemental_gold_path",
    "validate_dataset_record",
    "verify_training_gate",
]


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
