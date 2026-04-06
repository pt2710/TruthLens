from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from truthlens_data_pipeline.paths import read_json, relative_path, repo_root, utc_now, write_json, write_jsonl
from truthlens_dataset_governance import (
    build_supplemental_candidate_batch,
    supplemental_adjudication_path,
    supplemental_gold_path,
)
from truthlens_shared_schemas.contracts import ContentClass

QUEUE_NAME_TO_KEY = {
    "review": "review_queue",
    "hard-negative": "hard_negative_queue",
    "disagreement": "disagreement_queue",
}
QUEUE_KEY_TO_NAME = {value: key for key, value in QUEUE_NAME_TO_KEY.items()}
RISK_LABEL_KEYS = (
    "clickbait",
    "misleading_thumbnail",
    "misleading_title",
    "fearbait",
    "ai_mass_spam",
    "deceptive_divergence",
)
ADJUDICATION_RESOLUTIONS = {
    "confirmed-risk",
    "confirmed-benign",
    "needs-escalation",
}
CONTENT_CLASS_VALUES = {content_class.value for content_class in ContentClass}


class AnnotationDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    queue_name: Literal["review", "hard-negative", "disagreement"]
    resolution: Literal["confirmed-risk", "confirmed-benign", "needs-escalation"]
    content_class: str = Field(default="unknown", min_length=1)
    label_overrides: dict[str, bool] = Field(default_factory=dict)
    bias_review_required: bool | None = None
    reviewer: str | None = None
    note: str | None = None
    decided_at: str | None = None


class SaveAnnotationAdjudicationsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    reviewer: str | None = None
    decisions: list[AnnotationDecisionPayload] = Field(default_factory=list)


class SaveAnnotationAdjudicationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    saved_at: str
    saved_count: int
    adjudication_path: str
    gold_path: str
    supplemental_adjudication_path: str | None = None
    supplemental_gold_path: str | None = None
    summary: dict[str, Any]


def _latest_annotation_batch_path() -> Path:
    return repo_root() / "datasets" / "labels" / "annotation_batches" / "latest.json"


def _fallback_annotation_batch_path() -> Path:
    return repo_root() / "apps" / "labeling-ui" / "public" / "annotation-batch.json"


def _load_latest_annotation_batch() -> dict[str, Any]:
    latest_path = _latest_annotation_batch_path()
    if latest_path.exists():
        return read_json(latest_path)
    fallback_path = _fallback_annotation_batch_path()
    if fallback_path.exists():
        return read_json(fallback_path)
    raise FileNotFoundError("No annotation batch payload is available in this workspace.")


def _load_latest_build_manifest() -> dict[str, Any] | None:
    path = repo_root() / "datasets" / "manifests" / "builds" / "latest.json"
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _normalize_content_class(value: str | None) -> str:
    candidate = (value or "unknown").strip().lower()
    return candidate if candidate in CONTENT_CLASS_VALUES else "unknown"


def _normalize_label_overrides(value: dict[str, Any] | None) -> dict[str, bool]:
    overrides: dict[str, bool] = {}
    if not isinstance(value, dict):
        return overrides
    for key, raw_value in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw_value, bool):
            overrides[key] = raw_value
    return overrides


def _entry_lookup(batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for queue_key, queue_name in QUEUE_KEY_TO_NAME.items():
        for item in batch.get(queue_key, []):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("item_id", "")).strip()
            if not item_id:
                continue
            lookup[item_id] = {
                **item,
                "queue_name": queue_name,
            }
    return lookup


def _hydrate_pipeline_candidate(
    item: dict[str, Any],
    *,
    queue_name: str,
    run_id: str,
    generated_at: str | None,
    source_batch_path: str | None,
) -> dict[str, Any]:
    return {
        "candidate_id": str(item.get("candidate_id") or item.get("item_id")),
        "item_id": str(item.get("item_id", "")),
        "queue_name": queue_name,
        "origin": str(item.get("origin") or "pipeline-batch"),
        "title": str(item.get("title", "")),
        "channel_name": item.get("channel_name"),
        "weak_label_score": item.get("weak_label_score"),
        "uncertainty_bucket": item.get("uncertainty_bucket"),
        "source_trust_flag": item.get("source_trust_flag"),
        "template_cluster": item.get("template_cluster"),
        "prior_flags": item.get("prior_flags"),
        "content_class": str(item.get("content_class", "unknown")),
        "content_class_confidence": item.get("content_class_confidence"),
        "dominant_bias_risk": item.get("dominant_bias_risk"),
        "bias_review_required": item.get("bias_review_required"),
        "current_labels": dict(item.get("current_labels", {})),
        "annotator_notes": list(item.get("annotator_notes", [])),
        "queue_reason": item.get("queue_reason"),
        "distilled_features": item.get("distilled_features"),
        "feedback_summary": dict(
            item.get(
                "feedback_summary",
                {
                    "total_events": 0,
                    "risk_event_count": 0,
                    "benign_event_count": 0,
                    "manual_report_count": 0,
                    "last_user_action": None,
                },
            )
        ),
        "provenance": dict(
            item.get(
                "provenance",
                {
                    "generated_at": generated_at or utc_now(),
                    "generator": "pipeline-annotation-batch-v1",
                    "candidate_sources": ["pipeline-batch"],
                    "observation_ids": [],
                    "feedback_event_ids": [],
                    "source_paths": [source_batch_path] if source_batch_path else [],
                },
            )
        ),
        "split_safety": dict(
            item.get(
                "split_safety",
                {
                    "dataset_membership": "existing-batch",
                    "split_status": "assigned",
                    "split_name": "unknown",
                    "dataset_build_id": None,
                    "annotation_run_id": run_id,
                    "eligible_for_training": False,
                    "leakage_guard_reason": (
                        "Adjudication affects current review artifacts only. Supplemental intake must still be ingested through deterministic dataset governance before any future training use."
                    ),
                },
            )
        ),
    }


def _candidate_adjudication_paths(run_id: str) -> list[Path]:
    root = repo_root()
    candidates = [
        root / "datasets" / "labels" / "adjudication" / f"{run_id}.json",
        root / "datasets" / "labels" / "adjudication" / "latest.json",
    ]
    build_manifest = _load_latest_build_manifest()
    if build_manifest and str(build_manifest.get("run_id")) == run_id:
        adjudication_artifact = str(build_manifest.get("artifacts", {}).get("adjudication", "")).strip()
        if adjudication_artifact:
            candidates.insert(0, root / adjudication_artifact)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key not in seen:
            deduped.append(path)
            seen.add(key)
    return deduped


def _candidate_gold_paths(run_id: str) -> list[Path]:
    root = repo_root()
    candidates = [
        root / "datasets" / "labels" / "gold" / f"{run_id}-adjudicated.jsonl",
        root / "datasets" / "labels" / "gold" / "latest.jsonl",
    ]
    build_manifest = _load_latest_build_manifest()
    if build_manifest and str(build_manifest.get("run_id")) == run_id:
        gold_artifact = str(build_manifest.get("artifacts", {}).get("gold", "")).strip()
        if gold_artifact:
            candidates.insert(0, root / gold_artifact)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key not in seen:
            deduped.append(path)
            seen.add(key)
    return deduped


def _load_current_adjudications(run_id: str) -> dict[str, Any] | None:
    for path in _candidate_adjudication_paths(run_id):
        if not path.exists():
            continue
        payload = read_json(path)
        if isinstance(payload, dict) and str(payload.get("run_id", "")).strip() == run_id:
            return payload
    return None


def _load_current_supplemental_adjudications(run_id: str) -> dict[str, Any] | None:
    path = supplemental_adjudication_path(run_id)
    if not path.exists():
        return None
    payload = read_json(path)
    if isinstance(payload, dict) and str(payload.get("run_id", "")).strip() == run_id:
        return payload
    return None


def _merged_label_snapshot(entry: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    labels: dict[str, Any] = {
        key: bool(value)
        for key, value in dict(entry.get("current_labels", {})).items()
        if isinstance(key, str)
    }
    labels.update(_normalize_label_overrides(decision.get("label_overrides")))
    if decision.get("bias_review_required") is not None:
        labels["bias_review_required"] = bool(decision["bias_review_required"])
    labels["content_class"] = _normalize_content_class(str(decision.get("content_class", entry.get("content_class", "unknown"))))

    resolution = str(decision.get("resolution", "needs-escalation"))
    if resolution == "confirmed-benign":
        for label_key in RISK_LABEL_KEYS:
            labels[label_key] = False
        labels["review_required"] = False
        labels["bias_review_required"] = bool(decision.get("bias_review_required", False))
    elif resolution == "confirmed-risk":
        labels["review_required"] = False
        if not any(bool(labels.get(label_key, False)) for label_key in RISK_LABEL_KEYS):
            labels["clickbait"] = True
    else:
        labels["review_required"] = True
        labels["bias_review_required"] = bool(decision.get("bias_review_required", True))
    return labels


def _build_adjudication_summary(
    entry_lookup: dict[str, dict[str, Any]],
    adjudications: list[dict[str, Any]],
) -> dict[str, Any]:
    resolution_counts = Counter(str(item.get("resolution", "needs-escalation")) for item in adjudications)
    queue_counts = Counter(str(item.get("queue_name", "review")) for item in adjudications)
    class_counts = Counter(str(item.get("content_class", "unknown")) for item in adjudications)
    confirmed_count = sum(
        1
        for item in adjudications
        if str(item.get("resolution")) in {"confirmed-risk", "confirmed-benign"}
    )
    return {
        "saved_count": len(adjudications),
        "confirmed_count": confirmed_count,
        "escalation_count": int(resolution_counts.get("needs-escalation", 0)),
        "unresolved_count": max(len(entry_lookup) - confirmed_count, 0),
        "resolution_counts": dict(sorted(resolution_counts.items())),
        "queue_counts": dict(sorted(queue_counts.items())),
        "content_class_counts": dict(sorted(class_counts.items())),
    }


def _build_decision_record(
    decision: dict[str, Any],
    *,
    entry: dict[str, Any],
    reviewer: str | None,
    saved_at: str,
) -> dict[str, Any]:
    return {
        "item_id": str(decision["item_id"]),
        "candidate_id": str(entry.get("candidate_id", entry.get("item_id", ""))),
        "queue_name": str(decision["queue_name"]),
        "resolution": str(decision["resolution"])
        if str(decision["resolution"]) in ADJUDICATION_RESOLUTIONS
        else "needs-escalation",
        "content_class": _normalize_content_class(str(decision.get("content_class", ""))),
        "label_overrides": _normalize_label_overrides(decision.get("label_overrides")),
        "bias_review_required": decision.get("bias_review_required"),
        "reviewer": str(decision.get("reviewer") or reviewer or "").strip() or None,
        "note": str(decision.get("note") or "").strip() or None,
        "decided_at": str(decision.get("decided_at") or saved_at),
        "title": str(entry.get("title", "")),
        "channel_name": str(entry.get("channel_name", "")),
        "dominant_bias_risk": str(entry.get("dominant_bias_risk", "balanced-context")),
        "suggested_content_class": str(entry.get("content_class", "unknown")),
        "origin": str(entry.get("origin", "pipeline-batch")),
    }


def _build_gold_row(
    *,
    entry: dict[str, Any],
    decision: dict[str, Any],
    label_snapshot: dict[str, Any],
    source_batch_path: str | None,
) -> dict[str, Any]:
    return {
        "item_id": decision["item_id"],
        "candidate_id": entry.get("candidate_id"),
        "queue_name": decision["queue_name"],
        "resolution": decision["resolution"],
        "content_class": label_snapshot["content_class"],
        "labels": label_snapshot,
        "reviewer": decision.get("reviewer"),
        "note": decision.get("note"),
        "decided_at": decision.get("decided_at"),
        "title": entry.get("title"),
        "channel_name": entry.get("channel_name"),
        "dominant_bias_risk": entry.get("dominant_bias_risk"),
        "origin": entry.get("origin", "pipeline-batch"),
        "source_batch_path": source_batch_path,
        "provenance": entry.get("provenance"),
        "split_safety": entry.get("split_safety"),
    }


def build_annotation_batch_response() -> dict[str, Any]:
    batch = _load_latest_annotation_batch()
    run_id = str(batch.get("run_id", "")).strip()
    if not run_id:
        raise FileNotFoundError("Latest annotation batch payload is missing a run_id.")
    supplemental_payload = build_supplemental_candidate_batch(run_id)
    response_payload = {
        **batch,
        "review_queue": [
            _hydrate_pipeline_candidate(
                dict(item),
                queue_name="review",
                run_id=run_id,
                generated_at=str(batch.get("generated_at") or ""),
                source_batch_path=str(batch.get("source_batch_path") or ""),
            )
            for item in batch.get("review_queue", [])
            if isinstance(item, dict)
        ],
        "hard_negative_queue": [
            _hydrate_pipeline_candidate(
                dict(item),
                queue_name="hard-negative",
                run_id=run_id,
                generated_at=str(batch.get("generated_at") or ""),
                source_batch_path=str(batch.get("source_batch_path") or ""),
            )
            for item in batch.get("hard_negative_queue", [])
            if isinstance(item, dict)
        ],
        "disagreement_queue": [
            _hydrate_pipeline_candidate(
                dict(item),
                queue_name="disagreement",
                run_id=run_id,
                generated_at=str(batch.get("generated_at") or ""),
                source_batch_path=str(batch.get("source_batch_path") or ""),
            )
            for item in batch.get("disagreement_queue", [])
            if isinstance(item, dict)
        ],
    }
    for queue_key in QUEUE_KEY_TO_NAME:
        response_payload[queue_key].extend(
            [
                dict(item)
                for item in supplemental_payload.get("supplemental_candidates", {}).get(queue_key, [])
                if isinstance(item, dict)
            ]
        )
    adjudication_payload = _load_current_adjudications(run_id)
    supplemental_adjudication_payload = _load_current_supplemental_adjudications(run_id)
    entry_lookup = _entry_lookup(response_payload)
    adjudication_by_item = {
        str(item.get("item_id", "")): item
        for item in adjudication_payload.get("adjudications", [])
        if isinstance(item, dict)
    } if isinstance(adjudication_payload, dict) else {}
    if isinstance(supplemental_adjudication_payload, dict):
        adjudication_by_item.update(
            {
                str(item.get("item_id", "")): item
                for item in supplemental_adjudication_payload.get("adjudications", [])
                if isinstance(item, dict)
            }
        )
    for queue_key in QUEUE_KEY_TO_NAME:
        for item in response_payload.get(queue_key, []):
            item.setdefault("current_labels", {})
            item.setdefault("annotator_notes", [])
            adjudication = adjudication_by_item.get(str(item.get("item_id", "")))
            if adjudication is not None:
                item["adjudication"] = adjudication
    response_payload["adjudication_summary"] = _build_adjudication_summary(
        entry_lookup,
        list(adjudication_by_item.values()),
    )
    response_payload["supplemental_candidate_batch_path"] = supplemental_payload.get("candidate_batch_path")
    response_payload["supplemental_summary"] = supplemental_payload.get("summary", {})
    if adjudication_payload is not None:
        response_payload["adjudication_path"] = str(adjudication_payload.get("adjudication_path") or "")
        response_payload["gold_path"] = str(adjudication_payload.get("gold_path") or "")
    if supplemental_adjudication_payload is not None:
        response_payload["supplemental_adjudication_path"] = str(
            supplemental_adjudication_payload.get("adjudication_path") or ""
        )
        response_payload["supplemental_gold_path"] = str(
            supplemental_adjudication_payload.get("gold_path") or ""
        )
    return response_payload


def save_annotation_adjudications(
    payload: SaveAnnotationAdjudicationsRequest,
) -> SaveAnnotationAdjudicationsResponse:
    batch = _load_latest_annotation_batch()
    batch_run_id = str(batch.get("run_id", "")).strip()
    if payload.run_id != batch_run_id:
        raise ValueError(
            f"Annotation run '{payload.run_id}' does not match the latest batch '{batch_run_id}'."
        )
    pipeline_batch = {
        "review_queue": [
            _hydrate_pipeline_candidate(
                dict(item),
                queue_name="review",
                run_id=payload.run_id,
                generated_at=str(batch.get("generated_at") or ""),
                source_batch_path=str(batch.get("source_batch_path") or ""),
            )
            for item in batch.get("review_queue", [])
            if isinstance(item, dict)
        ],
        "hard_negative_queue": [
            _hydrate_pipeline_candidate(
                dict(item),
                queue_name="hard-negative",
                run_id=payload.run_id,
                generated_at=str(batch.get("generated_at") or ""),
                source_batch_path=str(batch.get("source_batch_path") or ""),
            )
            for item in batch.get("hard_negative_queue", [])
            if isinstance(item, dict)
        ],
        "disagreement_queue": [
            _hydrate_pipeline_candidate(
                dict(item),
                queue_name="disagreement",
                run_id=payload.run_id,
                generated_at=str(batch.get("generated_at") or ""),
                source_batch_path=str(batch.get("source_batch_path") or ""),
            )
            for item in batch.get("disagreement_queue", [])
            if isinstance(item, dict)
        ],
    }
    supplemental_payload = build_supplemental_candidate_batch(payload.run_id)
    supplemental_batch = {
        "review_queue": list(supplemental_payload.get("supplemental_candidates", {}).get("review_queue", [])),
        "hard_negative_queue": list(
            supplemental_payload.get("supplemental_candidates", {}).get("hard_negative_queue", [])
        ),
        "disagreement_queue": list(
            supplemental_payload.get("supplemental_candidates", {}).get("disagreement_queue", [])
        ),
    }
    pipeline_lookup = _entry_lookup(pipeline_batch)
    supplemental_lookup = _entry_lookup(supplemental_batch)
    current_payload = _load_current_adjudications(payload.run_id) or {}
    current_supplemental_payload = _load_current_supplemental_adjudications(payload.run_id) or {}
    existing_by_item = {
        str(item.get("item_id", "")): item
        for item in current_payload.get("adjudications", [])
        if isinstance(item, dict)
    }
    supplemental_by_item = {
        str(item.get("item_id", "")): item
        for item in current_supplemental_payload.get("adjudications", [])
        if isinstance(item, dict)
    }
    saved_at = utc_now()
    for decision_model in payload.decisions:
        decision = decision_model.model_dump()
        item_id = str(decision["item_id"])
        if item_id in pipeline_lookup:
            entry = pipeline_lookup[item_id]
            queue_name = str(decision["queue_name"])
            expected_queue_name = str(entry["queue_name"])
            if queue_name != expected_queue_name:
                raise ValueError(
                    f"Item '{item_id}' belongs to queue '{expected_queue_name}', not '{queue_name}'."
                )
            existing_by_item[item_id] = _build_decision_record(
                decision,
                entry=entry,
                reviewer=payload.reviewer,
                saved_at=saved_at,
            )
            continue
        if item_id in supplemental_lookup:
            entry = supplemental_lookup[item_id]
            queue_name = str(decision["queue_name"])
            expected_queue_name = str(entry["queue_name"])
            if queue_name != expected_queue_name:
                raise ValueError(
                    f"Item '{item_id}' belongs to queue '{expected_queue_name}', not '{queue_name}'."
                )
            supplemental_by_item[item_id] = _build_decision_record(
                decision,
                entry=entry,
                reviewer=payload.reviewer,
                saved_at=saved_at,
            )
            continue
        if item_id not in pipeline_lookup and item_id not in supplemental_lookup:
            raise ValueError(f"Item '{item_id}' is not present in the latest annotation batch.")

    adjudications = sorted(
        existing_by_item.values(),
        key=lambda item: (str(item.get("queue_name", "")), str(item.get("item_id", ""))),
    )
    supplemental_adjudications = sorted(
        supplemental_by_item.values(),
        key=lambda item: (str(item.get("queue_name", "")), str(item.get("item_id", ""))),
    )
    summary = _build_adjudication_summary(pipeline_lookup, adjudications)
    supplemental_summary = _build_adjudication_summary(supplemental_lookup, supplemental_adjudications)
    gold_rows = []
    for decision in adjudications:
        if str(decision.get("resolution")) == "needs-escalation":
            continue
        entry = pipeline_lookup[str(decision["item_id"])]
        label_snapshot = _merged_label_snapshot(entry, decision)
        gold_rows.append(
            _build_gold_row(
                entry=entry,
                decision=decision,
                label_snapshot=label_snapshot,
                source_batch_path=batch.get("source_batch_path"),
            )
        )
    supplemental_gold_rows = []
    for decision in supplemental_adjudications:
        if str(decision.get("resolution")) == "needs-escalation":
            continue
        entry = supplemental_lookup[str(decision["item_id"])]
        label_snapshot = _merged_label_snapshot(entry, decision)
        supplemental_gold_rows.append(
            _build_gold_row(
                entry=entry,
                decision=decision,
                label_snapshot=label_snapshot,
                source_batch_path=supplemental_payload.get("candidate_batch_path"),
            )
        )

    adjudication_paths = _candidate_adjudication_paths(payload.run_id)
    gold_paths = _candidate_gold_paths(payload.run_id)
    supplemental_adjudication = supplemental_adjudication_path(payload.run_id)
    supplemental_gold = supplemental_gold_path(payload.run_id)
    adjudication_payload = {
        "run_id": payload.run_id,
        "generated_at": batch.get("generated_at"),
        "saved_at": saved_at,
        "reviewer": payload.reviewer,
        "source_batch_path": batch.get("source_batch_path"),
        "adjudication_path": relative_path(adjudication_paths[0]),
        "gold_path": relative_path(gold_paths[0]),
        "summary": summary,
        "adjudications": adjudications,
    }
    supplemental_adjudication_payload = {
        "run_id": payload.run_id,
        "generated_at": supplemental_payload.get("generated_at"),
        "saved_at": saved_at,
        "reviewer": payload.reviewer,
        "source_batch_path": supplemental_payload.get("candidate_batch_path"),
        "adjudication_path": relative_path(supplemental_adjudication),
        "gold_path": relative_path(supplemental_gold),
        "summary": supplemental_summary,
        "adjudications": supplemental_adjudications,
    }
    for path in adjudication_paths:
        write_json(path, adjudication_payload)
    for path in gold_paths:
        write_jsonl(path, gold_rows)
    write_json(supplemental_adjudication, supplemental_adjudication_payload)
    write_jsonl(supplemental_gold, supplemental_gold_rows)

    return SaveAnnotationAdjudicationsResponse(
        run_id=payload.run_id,
        saved_at=saved_at,
        saved_count=len(adjudications) + len(supplemental_adjudications),
        adjudication_path=relative_path(adjudication_paths[0]),
        gold_path=relative_path(gold_paths[0]),
        supplemental_adjudication_path=relative_path(supplemental_adjudication),
        supplemental_gold_path=relative_path(supplemental_gold),
        summary={
            **summary,
            "supplemental_candidate_count": supplemental_payload.get("summary", {}).get("candidate_count", 0),
            "supplemental_saved_count": supplemental_summary.get("saved_count", 0),
            "supplemental_confirmed_count": supplemental_summary.get("confirmed_count", 0),
            "supplemental_escalation_count": supplemental_summary.get("escalation_count", 0),
            "supplemental_unresolved_count": supplemental_summary.get("unresolved_count", 0),
        },
    )
