from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from truthlens_data_pipeline.paths import read_json, relative_path, repo_root, utc_now, write_json, write_jsonl
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


def build_annotation_batch_response() -> dict[str, Any]:
    batch = _load_latest_annotation_batch()
    run_id = str(batch.get("run_id", "")).strip()
    if not run_id:
        raise FileNotFoundError("Latest annotation batch payload is missing a run_id.")
    response_payload = {
        **batch,
        "review_queue": [dict(item) for item in batch.get("review_queue", [])],
        "hard_negative_queue": [dict(item) for item in batch.get("hard_negative_queue", [])],
        "disagreement_queue": [dict(item) for item in batch.get("disagreement_queue", [])],
    }
    adjudication_payload = _load_current_adjudications(run_id)
    entry_lookup = _entry_lookup(response_payload)
    adjudication_by_item = {
        str(item.get("item_id", "")): item
        for item in adjudication_payload.get("adjudications", [])
        if isinstance(item, dict)
    } if isinstance(adjudication_payload, dict) else {}
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
    if adjudication_payload is not None:
        response_payload["adjudication_path"] = str(adjudication_payload.get("adjudication_path") or "")
        response_payload["gold_path"] = str(adjudication_payload.get("gold_path") or "")
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
    entry_lookup = _entry_lookup(batch)
    current_payload = _load_current_adjudications(payload.run_id) or {}
    existing_by_item = {
        str(item.get("item_id", "")): item
        for item in current_payload.get("adjudications", [])
        if isinstance(item, dict)
    }
    saved_at = utc_now()
    for decision_model in payload.decisions:
        decision = decision_model.model_dump()
        item_id = str(decision["item_id"])
        if item_id not in entry_lookup:
            raise ValueError(f"Item '{item_id}' is not present in the latest annotation batch.")
        queue_name = str(decision["queue_name"])
        expected_queue_name = str(entry_lookup[item_id]["queue_name"])
        if queue_name != expected_queue_name:
            raise ValueError(
                f"Item '{item_id}' belongs to queue '{expected_queue_name}', not '{queue_name}'."
            )
        existing_by_item[item_id] = {
            "item_id": item_id,
            "queue_name": queue_name,
            "resolution": str(decision["resolution"])
            if str(decision["resolution"]) in ADJUDICATION_RESOLUTIONS
            else "needs-escalation",
            "content_class": _normalize_content_class(str(decision.get("content_class", ""))),
            "label_overrides": _normalize_label_overrides(decision.get("label_overrides")),
            "bias_review_required": decision.get("bias_review_required"),
            "reviewer": str(decision.get("reviewer") or payload.reviewer or "").strip() or None,
            "note": str(decision.get("note") or "").strip() or None,
            "decided_at": str(decision.get("decided_at") or saved_at),
            "title": str(entry_lookup[item_id].get("title", "")),
            "channel_name": str(entry_lookup[item_id].get("channel_name", "")),
            "dominant_bias_risk": str(entry_lookup[item_id].get("dominant_bias_risk", "balanced-context")),
            "suggested_content_class": str(entry_lookup[item_id].get("content_class", "unknown")),
        }

    adjudications = sorted(
        existing_by_item.values(),
        key=lambda item: (str(item.get("queue_name", "")), str(item.get("item_id", ""))),
    )
    summary = _build_adjudication_summary(entry_lookup, adjudications)
    gold_rows = []
    for decision in adjudications:
        if str(decision.get("resolution")) == "needs-escalation":
            continue
        entry = entry_lookup[str(decision["item_id"])]
        label_snapshot = _merged_label_snapshot(entry, decision)
        gold_rows.append(
            {
                "item_id": decision["item_id"],
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
                "source_batch_path": batch.get("source_batch_path"),
            }
        )

    adjudication_paths = _candidate_adjudication_paths(payload.run_id)
    gold_paths = _candidate_gold_paths(payload.run_id)
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
    for path in adjudication_paths:
        write_json(path, adjudication_payload)
    for path in gold_paths:
        write_jsonl(path, gold_rows)

    return SaveAnnotationAdjudicationsResponse(
        run_id=payload.run_id,
        saved_at=saved_at,
        saved_count=len(adjudications),
        adjudication_path=relative_path(adjudication_paths[0]),
        gold_path=relative_path(gold_paths[0]),
        summary=summary,
    )
