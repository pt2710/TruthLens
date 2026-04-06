from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from truthlens_data_pipeline.paths import read_json, relative_path, repo_root, utc_now, write_json
from truthlens_model_serving import load_browser_observations, load_feedback_events

RISK_FEEDBACK_ACTIONS = {"report", "confirm-report", "hide-locally", "mute-channel-local"}
BENIGN_FEEDBACK_ACTIONS = {"not-misleading", "undo-hide", "confirm-transparent"}
FACTUAL_CLASSES = {"news", "commentary", "documentary", "promo", "unknown"}


def _latest_annotation_batch_path() -> Path:
    return repo_root() / "datasets" / "labels" / "annotation_batches" / "latest.json"


def _latest_build_manifest() -> dict[str, Any] | None:
    path = repo_root() / "datasets" / "manifests" / "builds" / "latest.json"
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _candidate_batch_path(run_id: str) -> Path:
    return repo_root() / "datasets" / "labels" / "supplemental_candidates" / f"{run_id}.json"


def _latest_candidate_batch_path() -> Path:
    return repo_root() / "datasets" / "labels" / "supplemental_candidates" / "latest.json"


def supplemental_adjudication_path(run_id: str) -> Path:
    return repo_root() / "datasets" / "labels" / "supplemental_adjudication" / f"{run_id}.json"


def supplemental_gold_path(run_id: str) -> Path:
    return repo_root() / "datasets" / "labels" / "supplemental_gold" / f"{run_id}.jsonl"


def _stable_candidate_id(item_id: str) -> str:
    digest = hashlib.sha1(item_id.encode("utf-8")).hexdigest()[:12]
    return f"supplemental-{digest}"


def _token_count(value: str | None) -> int:
    if not value:
        return 0
    return len([token for token in value.strip().split() if token])


def _notable_observation(observation: dict[str, Any] | None) -> bool:
    if not isinstance(observation, dict):
        return False
    score_snapshot = observation.get("score_snapshot", {})
    if not isinstance(score_snapshot, dict):
        return False
    recommended_action = str(score_snapshot.get("recommended_action", "none"))
    risk_score = float(score_snapshot.get("risk_score", 0.0) or 0.0)
    uncertainty = float(score_snapshot.get("uncertainty", 0.0) or 0.0)
    return recommended_action != "none" or risk_score >= 0.55 or uncertainty >= 0.45


def _feedback_event_id(event: dict[str, Any]) -> str:
    feedback_id = str(event.get("feedback_id", "")).strip()
    if feedback_id:
        return feedback_id
    item_id = str(event.get("item_id", "")).strip() or "unknown-item"
    timestamp = str(event.get("timestamp", "")).strip() or "unknown-time"
    user_action = str(event.get("user_action", "")).strip() or "unknown-action"
    digest = hashlib.sha1(f"{item_id}:{timestamp}:{user_action}".encode("utf-8")).hexdigest()[:12]
    return f"feedback-{digest}"


def _issue_types(events: list[dict[str, Any]]) -> set[str]:
    issue_types: set[str] = set()
    for event in events:
        manual_report = event.get("manual_report")
        if not isinstance(manual_report, dict):
            continue
        for issue in manual_report.get("issues", []):
            if isinstance(issue, dict):
                issue_type = str(issue.get("issue_type", "")).strip().lower()
                if issue_type:
                    issue_types.add(issue_type)
    return issue_types


def _queue_name(risk_events: int, benign_events: int, notable_observation: bool) -> str:
    if risk_events and benign_events:
        return "disagreement"
    if benign_events and not risk_events and not notable_observation:
        return "hard-negative"
    return "review"


def _existing_batch_lookup(batch: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for queue_key, queue_name in (
        ("review_queue", "review"),
        ("hard_negative_queue", "hard-negative"),
        ("disagreement_queue", "disagreement"),
    ):
        for item in batch.get(queue_key, []):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("item_id", "")).strip()
            if item_id:
                lookup[item_id] = queue_name
    return lookup


def build_supplemental_candidate_batch(run_id: str | None = None) -> dict[str, Any]:
    annotation_path = _latest_annotation_batch_path()
    if not annotation_path.exists():
        payload: dict[str, Any] = {
            "run_id": run_id or "",
            "generated_at": utc_now(),
            "candidate_batch_path": None,
            "supplemental_candidates": {
                "review_queue": [],
                "hard_negative_queue": [],
                "disagreement_queue": [],
            },
            "summary": {
                "candidate_count": 0,
                "feedback_linked_count": 0,
                "observation_linked_count": 0,
                "split_blocked_count": 0,
                "manual_report_linked_count": 0,
            },
        }
        return payload

    annotation_batch = read_json(annotation_path)
    effective_run_id = run_id or str(annotation_batch.get("run_id", "")).strip()
    existing_lookup = _existing_batch_lookup(annotation_batch)
    observations = load_browser_observations()
    feedback_events = load_feedback_events()
    latest_build = _latest_build_manifest() or {}

    observations_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        item_id = str(observation.get("item_id", "")).strip()
        if item_id:
            observations_by_item[item_id].append(observation)

    feedback_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in feedback_events:
        item_id = str(event.get("item_id", "")).strip()
        if item_id:
            feedback_by_item[item_id].append(event)

    candidate_queues: dict[str, list[dict[str, Any]]] = {
        "review_queue": [],
        "hard_negative_queue": [],
        "disagreement_queue": [],
    }
    feedback_linked_count = 0
    observation_linked_count = 0
    manual_report_linked_count = 0

    for item_id in sorted(set(observations_by_item) | set(feedback_by_item)):
        if item_id in existing_lookup:
            continue
        item_observations = sorted(
            observations_by_item.get(item_id, []),
            key=lambda observation: str(observation.get("provenance", {}).get("observed_at", "")),
        )
        item_feedback = sorted(
            feedback_by_item.get(item_id, []),
            key=lambda event: str(event.get("timestamp", "")),
        )
        latest_observation = item_observations[-1] if item_observations else None
        notable_observation = _notable_observation(latest_observation)
        risk_events = sum(
            1
            for event in item_feedback
            if str(event.get("user_action", "")).strip().lower() in RISK_FEEDBACK_ACTIONS
        )
        benign_events = sum(
            1
            for event in item_feedback
            if str(event.get("user_action", "")).strip().lower() in BENIGN_FEEDBACK_ACTIONS
        )
        manual_reports = sum(1 for event in item_feedback if isinstance(event.get("manual_report"), dict))
        if risk_events == 0 and benign_events == 0 and not notable_observation:
            continue

        if item_feedback:
            feedback_linked_count += 1
        if latest_observation is not None:
            observation_linked_count += 1
        if manual_reports:
            manual_report_linked_count += 1

        score_snapshot = dict(latest_observation.get("score_snapshot", {})) if isinstance(latest_observation, dict) else {}
        distilled_features = (
            dict(latest_observation.get("distilled_features", {}))
            if isinstance(latest_observation, dict)
            else {}
        )
        title_snapshot = (
            str(latest_observation.get("title_snapshot", "")).strip()
            if isinstance(latest_observation, dict)
            else ""
        )
        channel_name = (
            str(latest_observation.get("channel_name", "")).strip() or None
            if isinstance(latest_observation, dict)
            else None
        )
        content_class = str(score_snapshot.get("content_class", "unknown") or "unknown")
        uncertainty = float(score_snapshot.get("uncertainty", 0.0) or 0.0)
        content_class_confidence = float(score_snapshot.get("content_class_confidence", 0.0) or 0.0)
        queue_name = _queue_name(risk_events, benign_events, notable_observation)
        issue_types = _issue_types(item_feedback)
        current_labels = {
            "clickbait": risk_events > 0,
            "deceptive_divergence": bool(
                issue_types.intersection({"thumbnail", "title", "description", "transcript", "channel"})
            )
            or (risk_events > 0 and content_class in FACTUAL_CLASSES),
            "stylistic_divergence": bool(issue_types.intersection({"other"})) and risk_events == 0,
            "bias_review_required": bool(
                uncertainty >= 0.45
                or content_class_confidence <= 0.45
                or queue_name == "disagreement"
            ),
            "review_required": queue_name != "hard-negative",
        }
        observation_ids = [
            str(observation.get("observation_id", "")).strip()
            for observation in item_observations
            if str(observation.get("observation_id", "")).strip()
        ]
        feedback_ids = [_feedback_event_id(event) for event in item_feedback]
        candidate_score = max(
            float(score_snapshot.get("risk_score", 0.0) or 0.0),
            min(1.0, risk_events * 0.2 + manual_reports * 0.15 + benign_events * 0.1),
        )
        queue_key = {
            "review": "review_queue",
            "hard-negative": "hard_negative_queue",
            "disagreement": "disagreement_queue",
        }[queue_name]
        candidate = {
            "candidate_id": _stable_candidate_id(item_id),
            "item_id": item_id,
            "queue_name": queue_name,
            "origin": "supplemental-intake",
            "title": title_snapshot or item_id,
            "channel_name": channel_name,
            "weak_label_score": round(candidate_score, 4),
            "uncertainty_bucket": "high" if uncertainty >= 0.45 else "medium" if uncertainty >= 0.25 else "low",
            "source_trust_flag": "runtime-supplemental-intake",
            "template_cluster": None,
            "prior_flags": None,
            "content_class": content_class,
            "content_class_confidence": round(content_class_confidence, 4),
            "dominant_bias_risk": "feedback-linked-review" if risk_events else "feedback-linked-benign",
            "bias_review_required": current_labels["bias_review_required"],
            "current_labels": current_labels,
            "annotator_notes": [
                f"Supplemental intake candidate derived from {len(item_observations)} browser observation(s) and {len(item_feedback)} feedback event(s).",
                f"Risk feedback={risk_events}, benign feedback={benign_events}, manual reports={manual_reports}.",
            ],
            "queue_reason": (
                "Conflicting browser/feedback signals require adjudication."
                if queue_name == "disagreement"
                else (
                    "Benign browser/feedback signal should be preserved as a hard negative candidate."
                    if queue_name == "hard-negative"
                    else "Browser observation and feedback signal produced a supplemental review candidate."
                )
            ),
            "distilled_features": {
                "card_index": distilled_features.get("card_index"),
                "link_kind": distilled_features.get("link_kind", "unknown"),
                "has_thumbnail": bool(distilled_features.get("has_thumbnail", False)),
                "has_description_snapshot": bool(
                    distilled_features.get("has_description_snapshot", False)
                ),
                "has_transcript_excerpt": bool(
                    distilled_features.get("has_transcript_excerpt", False)
                ),
                "title_token_count": int(
                    distilled_features.get("title_token_count", _token_count(title_snapshot))
                ),
                "description_token_count": int(
                    distilled_features.get("description_token_count", 0)
                ),
                "channel_known": bool(distilled_features.get("channel_known", channel_name is not None)),
                "duration_seconds": distilled_features.get("duration_seconds"),
            }
            if latest_observation is not None
            else None,
            "feedback_summary": {
                "total_events": len(item_feedback),
                "risk_event_count": risk_events,
                "benign_event_count": benign_events,
                "manual_report_count": manual_reports,
                "last_user_action": str(item_feedback[-1].get("user_action", "")).strip() or None
                if item_feedback
                else None,
            },
            "provenance": {
                "generated_at": utc_now(),
                "generator": "browser-feedback-intake-v1",
                "candidate_sources": [
                    *(
                        ["browser-observation"]
                        if item_observations
                        else []
                    ),
                    *(
                        ["feedback-event"]
                        if item_feedback
                        else []
                    ),
                    *(
                        ["manual-report"]
                        if manual_reports
                        else []
                    ),
                ],
                "observation_ids": observation_ids,
                "feedback_event_ids": feedback_ids,
                "source_paths": [
                    "artifacts/reports/browser_observations.jsonl",
                    "artifacts/reports/feedback_events.jsonl",
                ],
            },
            "split_safety": {
                "dataset_membership": "supplemental-intake",
                "split_status": "blocked-until-ingestion",
                "split_name": "unknown",
                "dataset_build_id": str(latest_build.get("build_id", "")).strip() or None,
                "annotation_run_id": effective_run_id or None,
                "eligible_for_training": False,
                "leakage_guard_reason": (
                    "Supplemental browser/feedback intake is never appended directly to train, validation, or test. Manual adjudication and future deterministic ingestion are required first."
                ),
            },
        }
        candidate_queues[queue_key].append(candidate)

    payload = {
        "run_id": effective_run_id,
        "generated_at": utc_now(),
        "candidate_batch_path": relative_path(_candidate_batch_path(effective_run_id))
        if effective_run_id
        else None,
        "supplemental_candidates": candidate_queues,
        "summary": {
            "candidate_count": sum(len(rows) for rows in candidate_queues.values()),
            "feedback_linked_count": feedback_linked_count,
            "observation_linked_count": observation_linked_count,
            "manual_report_linked_count": manual_report_linked_count,
            "split_blocked_count": sum(len(rows) for rows in candidate_queues.values()),
        },
    }
    if effective_run_id:
        write_json(_candidate_batch_path(effective_run_id), payload)
        write_json(_latest_candidate_batch_path(), payload)
    return payload
