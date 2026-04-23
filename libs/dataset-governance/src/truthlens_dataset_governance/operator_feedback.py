from __future__ import annotations

import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from truthlens_data_pipeline.paths import (
    make_run_id,
    read_json,
    read_jsonl,
    relative_path,
    repo_root,
    utc_now,
    write_json,
    write_jsonl,
)
from truthlens_feature_extractors import (
    build_bias_primitives,
    class_adjusted_mismatch,
    count_sensational_tokens,
    dominant_bias_name,
    infer_bseo_prior_frames,
    infer_content_taxonomy,
    normalize_text,
    transcript_mismatch_score,
    transcript_overlap,
    uppercase_ratio,
)
from truthlens_model_serving import load_browser_observations, load_feedback_events, summarize_feedback_events

from .validators import validate_dataset_record

RISK_ACTION_MAP = {
    "confirm-report": "confirmed-risk",
    "confirm-transparent": "confirmed-benign",
}
PACKAGING_ISSUES = {"thumbnail", "title", "description", "transcript", "channel"}


def _normalized_feedback_actor(event: dict[str, Any]) -> dict[str, Any]:
    actor = event.get("feedback_actor")
    if not isinstance(actor, dict):
        return {
            "role": "end-user",
            "operator_id": None,
            "capture_scope": "local-only",
        }
    role = str(actor.get("role", "end-user")).strip().lower()
    capture_scope = str(actor.get("capture_scope", "local-only")).strip().lower()
    operator_id = str(actor.get("operator_id", "")).strip() or None
    if role != "creator-operator":
        return {
            "role": "end-user",
            "operator_id": None,
            "capture_scope": "local-only",
        }
    if capture_scope != "creator-candidate":
        capture_scope = "local-only"
    return {
        "role": "creator-operator",
        "operator_id": operator_id,
        "capture_scope": capture_scope,
    }


def _operator_mode() -> str:
    return os.getenv("TRUTHLENS_OPERATOR_MODE", "end-user").strip().lower()


def _operator_id() -> str | None:
    return os.getenv("TRUTHLENS_OPERATOR_ID", "").strip() or None


def _real_watch_url(item_id: str) -> bool:
    try:
        parsed = urlparse(item_id)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() not in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
        return False
    if parsed.path != "/watch":
        return False
    query = parse_qs(parsed.query)
    return bool(query.get("v"))


def _feedback_event_id(event: dict[str, Any]) -> str:
    feedback_id = str(event.get("feedback_id", "")).strip()
    if feedback_id:
        return feedback_id
    item_id = str(event.get("item_id", "")).strip() or "unknown-item"
    timestamp = str(event.get("timestamp", "")).strip() or "unknown-time"
    user_action = str(event.get("user_action", "")).strip() or "unknown-action"
    digest = hashlib.sha1(f"{item_id}:{timestamp}:{user_action}".encode("utf-8")).hexdigest()[:12]
    return f"feedback-{digest}"


def _operator_candidate_event(event: dict[str, Any]) -> tuple[bool, str]:
    actor = _normalized_feedback_actor(event)
    if (
        actor["role"] == "creator-operator"
        and actor["capture_scope"] == "creator-candidate"
        and actor["operator_id"]
    ):
        return True, "explicit-actor"
    if _operator_mode() != "creator-operator" or not _operator_id():
        return False, "operator-config-missing"
    runtime_context = event.get("runtime_context")
    manual_report = event.get("manual_report")
    if not isinstance(runtime_context, dict):
        return False, "runtime-context-missing"
    if not isinstance(manual_report, dict):
        return False, "manual-report-missing"
    if str(runtime_context.get("surface", "")).strip() != "extension-watch":
        return False, "surface-not-extension-watch"
    if str(event.get("model_version", "")).strip() != "extension-runtime":
        return False, "model-version-mismatch"
    item_id = str(event.get("item_id", "")).strip()
    if not _real_watch_url(item_id):
        return False, "item-id-not-real-watch-url"
    return True, "curated-backfill"


def _operator_feedback_manifest_path(run_id: str) -> Path:
    return repo_root() / "datasets" / "manifests" / "operator_feedback" / f"{run_id}.json"


def _latest_operator_feedback_manifest_path() -> Path:
    return repo_root() / "datasets" / "manifests" / "operator_feedback" / "latest.json"


def operator_adjudication_path(run_id: str) -> Path:
    return (
        repo_root()
        / "datasets"
        / "manifests"
        / "operator_feedback"
        / "adjudication"
        / f"{run_id}.json"
    )


def operator_gold_path(run_id: str) -> Path:
    return (
        repo_root()
        / "datasets"
        / "manifests"
        / "operator_feedback"
        / "gold"
        / f"{run_id}.jsonl"
    )


def _latest_operator_adjudication_path() -> Path:
    return (
        repo_root()
        / "datasets"
        / "manifests"
        / "operator_feedback"
        / "adjudication"
        / "latest.json"
    )


def _latest_operator_gold_path() -> Path:
    return (
        repo_root()
        / "datasets"
        / "manifests"
        / "operator_feedback"
        / "gold"
        / "latest.jsonl"
    )


def _observation_lookup() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    observations = load_browser_observations()
    by_observation_id: dict[str, dict[str, Any]] = {}
    by_item_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        observation_id = str(observation.get("observation_id", "")).strip()
        item_id = str(observation.get("item_id", "")).strip()
        if observation_id:
            by_observation_id[observation_id] = observation
        if item_id:
            by_item_id[item_id].append(observation)
    for item_id, rows in by_item_id.items():
        by_item_id[item_id] = sorted(
            rows,
            key=lambda row: str(row.get("provenance", {}).get("observed_at", "")),
        )
    return by_observation_id, by_item_id


def _issue_types(event: dict[str, Any]) -> set[str]:
    manual_report = event.get("manual_report")
    if not isinstance(manual_report, dict):
        return set()
    issues = manual_report.get("issues", [])
    normalized: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_type = str(issue.get("issue_type", "")).strip().lower()
        if issue_type:
            normalized.add(issue_type)
    return normalized


def _selected_tags(event: dict[str, Any]) -> list[str]:
    manual_report = event.get("manual_report")
    if not isinstance(manual_report, dict):
        return []
    return sorted(
        {
            str(tag).strip()
            for tag in manual_report.get("selected_tags", [])
            if str(tag).strip()
        }
    )


def _gold_labels(
    *,
    event: dict[str, Any],
    observation: dict[str, Any] | None,
    resolution: str,
) -> dict[str, Any]:
    score_snapshot = dict(observation.get("score_snapshot", {})) if isinstance(observation, dict) else {}
    issue_types = _issue_types(event)
    selected_tags = _selected_tags(event)
    content_class = str(
        score_snapshot.get("content_class")
        or dict(observation.get("score_snapshot", {})).get("content_class")
        if isinstance(observation, dict)
        else "unknown"
    ).strip() or "unknown"
    if resolution == "confirmed-benign":
        return {
            "clickbait": False,
            "misleading_thumbnail": False,
            "misleading_title": False,
            "fearbait": False,
            "ai_mass_spam": False,
            "content_class": content_class,
            "deceptive_divergence": False,
            "stylistic_divergence": False,
            "bias_review_required": False,
            "review_required": False,
        }
    return {
        "clickbait": bool(selected_tags) or True,
        "misleading_thumbnail": "thumbnail" in issue_types,
        "misleading_title": "title" in issue_types,
        "fearbait": bool(issue_types.intersection({"title", "thumbnail"})),
        "ai_mass_spam": False,
        "content_class": content_class,
        "deceptive_divergence": bool(issue_types.intersection(PACKAGING_ISSUES)),
        "stylistic_divergence": False,
        "bias_review_required": False,
        "review_required": False,
    }


def materialize_operator_feedback_artifacts(run_id: str | None = None) -> dict[str, Any]:
    resolved_run_id = run_id or make_run_id("operator-feedback")
    feedback_rows = load_feedback_events()
    by_observation_id, by_item_id = _observation_lookup()
    selected_events: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    for event in feedback_rows:
        accepted, reason = _operator_candidate_event(event)
        if not accepted:
            rejection_counts[reason] += 1
            continue
        action = str(event.get("user_action", "")).strip().lower()
        if action not in RISK_ACTION_MAP:
            rejection_counts["action-not-confirmed"] += 1
            continue
        feedback_id = _feedback_event_id(event)
        observation_id = str(event.get("observation_id", "")).strip() or None
        observation = by_observation_id.get(observation_id) if observation_id else None
        if observation is None:
            item_rows = by_item_id.get(str(event.get("item_id", "")).strip(), [])
            observation = item_rows[-1] if item_rows else None
        actor = _normalized_feedback_actor(event)
        selected_events.append(
            {
                "feedback_id": feedback_id,
                "item_id": str(event.get("item_id", "")).strip(),
                "observation_id": observation_id,
                "channel_name": str(event.get("channel_name", "")).strip() or None,
                "timestamp": str(event.get("timestamp", "")).strip() or None,
                "user_action": action,
                "resolution": RISK_ACTION_MAP[action],
                "selection_reason": reason,
                "operator_id": actor.get("operator_id") or _operator_id(),
                "actor": actor,
                "selected_tags": _selected_tags(event),
                "issue_types": sorted(_issue_types(event)),
                "requested_outcome": (
                    str(event.get("manual_report", {}).get("requested_outcome", "")).strip().lower() or None
                    if isinstance(event.get("manual_report"), dict)
                    else None
                ),
                "observation_found": observation is not None,
            }
        )

    selected_events.sort(key=lambda row: (str(row.get("timestamp") or ""), str(row.get("feedback_id") or "")))
    manifest_payload = {
        "run_id": resolved_run_id,
        "generated_at": utc_now(),
        "selection_mode": "curated-backfill",
        "operator_mode": _operator_mode(),
        "operator_id": _operator_id(),
        "selection_filters": {
            "explicit_actor_creator_candidate": True,
            "legacy_curated_backfill": {
                "runtime_context.surface": "extension-watch",
                "manual_report_required": True,
                "model_version": "extension-runtime",
                "item_id_must_be_real_youtube_watch_url": True,
                "user_action_in": sorted(RISK_ACTION_MAP),
            },
        },
        "source_paths": {
            "feedback_events": relative_path(repo_root() / "artifacts" / "reports" / "feedback_events.jsonl"),
            "browser_observations": relative_path(repo_root() / "artifacts" / "reports" / "browser_observations.jsonl"),
        },
        "selected_count": len(selected_events),
        "selected_feedback_ids": [str(row["feedback_id"]) for row in selected_events],
        "selected_action_counts": dict(sorted(Counter(str(row["user_action"]) for row in selected_events).items())),
        "selected_channels": dict(sorted(Counter(str(row.get("channel_name") or "Unknown channel") for row in selected_events).items())),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "events": selected_events,
    }
    manifest_path = write_json(_operator_feedback_manifest_path(resolved_run_id), manifest_payload)
    write_json(_latest_operator_feedback_manifest_path(), manifest_payload)

    adjudications: list[dict[str, Any]] = []
    gold_rows: list[dict[str, Any]] = []
    for selected in selected_events:
        item_rows = by_item_id.get(str(selected["item_id"]), [])
        observation = by_observation_id.get(str(selected.get("observation_id") or "")) or (
            item_rows[-1] if item_rows else None
        )
        feedback_event = next(
            (
                row
                for row in feedback_rows
                if _feedback_event_id(row) == str(selected["feedback_id"])
            ),
            None,
        )
        if feedback_event is None:
            continue
        reviewer = str(selected.get("operator_id") or _operator_id() or "operator-unset")
        labels = _gold_labels(
            event=feedback_event,
            observation=observation,
            resolution=str(selected["resolution"]),
        )
        adjudications.append(
            {
                "item_id": selected["item_id"],
                "feedback_id": selected["feedback_id"],
                "observation_id": selected.get("observation_id"),
                "queue_name": "operator-feedback",
                "resolution": selected["resolution"],
                "content_class": labels["content_class"],
                "reviewer": reviewer,
                "decided_at": selected.get("timestamp"),
                "origin": "creator-operator-feedback",
                "selected_tags": list(selected.get("selected_tags", [])),
                "issue_types": list(selected.get("issue_types", [])),
            }
        )
        gold_rows.append(
            {
                "item_id": selected["item_id"],
                "feedback_id": selected["feedback_id"],
                "observation_id": selected.get("observation_id"),
                "queue_name": "operator-feedback",
                "resolution": selected["resolution"],
                "content_class": labels["content_class"],
                "labels": labels,
                "reviewer": reviewer,
                "decided_at": selected.get("timestamp"),
                "title": observation.get("title_snapshot") if isinstance(observation, dict) else None,
                "channel_name": (
                    observation.get("channel_name")
                    if isinstance(observation, dict)
                    else selected.get("channel_name")
                ),
                "origin": "creator-operator-feedback",
                "source_batch_path": relative_path(manifest_path),
                "provenance": {
                    "operator_feedback_manifest_path": relative_path(manifest_path),
                    "feedback_event_ids": [selected["feedback_id"]],
                    "observation_ids": [selected["observation_id"]] if selected.get("observation_id") else [],
                    "selected_tags": list(selected.get("selected_tags", [])),
                    "issue_types": list(selected.get("issue_types", [])),
                    "operator_id": reviewer,
                    "selection_reason": selected.get("selection_reason"),
                },
                "split_safety": {
                    "dataset_membership": "creator-operator-candidate",
                    "split_status": "eligible-for-deterministic-ingestion",
                    "split_name": "unassigned",
                    "dataset_build_id": None,
                    "annotation_run_id": resolved_run_id,
                    "eligible_for_training": True,
                    "leakage_guard_reason": (
                        "Only creator/operator-confirmed feedback that has been materialized and adjudicated through the explicit operator pipeline is eligible for dataset ingestion."
                    ),
                },
            }
        )

    adjudication_payload = {
        "run_id": resolved_run_id,
        "generated_at": utc_now(),
        "source_manifest_path": relative_path(manifest_path),
        "adjudication_path": relative_path(operator_adjudication_path(resolved_run_id)),
        "gold_path": relative_path(operator_gold_path(resolved_run_id)),
        "summary": {
            "candidate_count": len(selected_events),
            "saved_count": len(adjudications),
            "confirmed_count": len(adjudications),
            "confirmed_risk_count": sum(1 for row in adjudications if row["resolution"] == "confirmed-risk"),
            "confirmed_benign_count": sum(1 for row in adjudications if row["resolution"] == "confirmed-benign"),
        },
        "adjudications": adjudications,
    }
    write_json(operator_adjudication_path(resolved_run_id), adjudication_payload)
    write_json(_latest_operator_adjudication_path(), adjudication_payload)
    write_jsonl(operator_gold_path(resolved_run_id), gold_rows)
    write_jsonl(_latest_operator_gold_path(), gold_rows)
    return adjudication_payload


def load_latest_operator_feedback_manifest() -> dict[str, Any] | None:
    path = _latest_operator_feedback_manifest_path()
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _load_latest_operator_adjudication() -> dict[str, Any] | None:
    path = _latest_operator_adjudication_path()
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _load_latest_operator_gold() -> list[dict[str, Any]]:
    path = _latest_operator_gold_path()
    if not path.exists():
        return []
    return [row for row in read_jsonl(path) if isinstance(row, dict)]


def _thumbnail_signal_path(build_id: str, feedback_id: str) -> Path:
    safe_feedback_id = feedback_id.replace("/", "-").replace("\\", "-")
    return repo_root() / "datasets" / "raw" / "thumbnails" / "operator-feedback" / f"{build_id}-{safe_feedback_id}.json"


def _write_thumbnail_signal(
    *,
    build_id: str,
    feedback_id: str,
    risk_seed: float,
) -> str:
    path = _thumbnail_signal_path(build_id, feedback_id)
    thumbnail_signal = {
        "brightness": 0.45,
        "saturation": round(0.2 + risk_seed * 0.65, 4),
        "contrast": round(0.24 + risk_seed * 0.5, 4),
        "text_density": round(0.18 + risk_seed * 0.55, 4),
        "face_emphasis": round(0.12 + risk_seed * 0.38, 4),
        "shock_indicator": round(0.1 + risk_seed * 0.62, 4),
        "entropy": 0.4,
        "aspect_ratio": round((16 / 9) / 2.5, 4),
        "byte_size": 128.0,
    }
    write_json(path, {"thumbnail_signal": thumbnail_signal})
    return relative_path(path)


def ingest_operator_feedback_records(
    *,
    build_id: str,
    run_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = load_latest_operator_feedback_manifest() or {}
    adjudication_payload = _load_latest_operator_adjudication() or {}
    gold_rows = _load_latest_operator_gold()
    if not gold_rows:
        empty_manifest = {
            "build_id": build_id,
            "run_id": run_id,
            "generated_at": utc_now(),
            "source_manifest_path": relative_path(_latest_operator_feedback_manifest_path())
            if _latest_operator_feedback_manifest_path().exists()
            else None,
            "source_adjudication_path": relative_path(_latest_operator_adjudication_path())
            if _latest_operator_adjudication_path().exists()
            else None,
            "source_gold_path": relative_path(_latest_operator_gold_path())
            if _latest_operator_gold_path().exists()
            else None,
            "ingested_count": 0,
            "skipped_count": 0,
            "operator_id": manifest.get("operator_id"),
            "record_path": None,
        }
        return [], empty_manifest

    feedback_summary = summarize_feedback_events(load_feedback_events())
    channel_profiles = dict(feedback_summary.get("channel_profiles", {}))
    by_observation_id, by_item_id = _observation_lookup()

    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for gold_row in gold_rows:
        provenance = dict(gold_row.get("provenance", {}))
        observation_ids = [str(value) for value in provenance.get("observation_ids", []) if str(value).strip()]
        observation = None
        for observation_id in observation_ids:
            observation = by_observation_id.get(observation_id)
            if observation is not None:
                break
        if observation is None:
            item_id = str(gold_row.get("item_id", "")).strip()
            item_rows = by_item_id.get(item_id, [])
            observation = item_rows[-1] if item_rows else None
        if observation is None:
            skipped.append(
                {
                    "item_id": gold_row.get("item_id"),
                    "feedback_id": gold_row.get("feedback_id"),
                    "reason": "missing-observation",
                }
            )
            continue

        score_snapshot = dict(observation.get("score_snapshot", {}))
        distilled_features = dict(observation.get("distilled_features", {}))
        metadata = dict(observation.get("metadata", {}))
        title = normalize_text(str(observation.get("title_snapshot", "")).strip())
        description = normalize_text(str(observation.get("description_snapshot", "")).strip())
        transcript = str(observation.get("transcript_excerpt", "")).strip() or description
        channel_name = str(
            observation.get("channel_name")
            or gold_row.get("channel_name")
            or "Unknown channel"
        ).strip() or "Unknown channel"
        channel_profile = dict(channel_profiles.get(channel_name.lower(), {}))
        prior_flags = int(channel_profile.get("reported_item_count", 0) or 0)
        scored_item_count = max(int(channel_profile.get("scored_item_count", 0) or 0), 1)
        trust_score = float(channel_profile.get("trust_score", 5.0) or 5.0)
        history_features = {
            "channel_uploads": scored_item_count,
            "channel_risk_mean": round(max(0.0, min(1.0, 1.0 - trust_score / 10.0)), 4),
            "publishing_velocity": round(scored_item_count / 7.0, 4),
            "recent_upload_velocity": round(scored_item_count / 7.0, 4),
            "repeat_template_rate": round(prior_flags / max(scored_item_count, 1), 4),
            "engagement_anomaly": 1.0,
        }
        taxonomy = infer_content_taxonomy(
            title=title,
            description=description,
            transcript=transcript,
            channel_name=channel_name,
            tags=[],
            hashtags=[],
            template_cluster="operator-feedback",
            channel_history_features={**history_features, "prior_flags": float(prior_flags)},
        )
        content_class = str(gold_row.get("labels", {}).get("content_class") or taxonomy["content_class"])
        content_class_confidence = float(
            score_snapshot.get("content_class_confidence", taxonomy["content_class_confidence"])
        )
        sensational_count = count_sensational_tokens(title)
        raw_transcript_mismatch = transcript_mismatch_score(title, transcript, sensational_count)
        adjusted_transcript_mismatch, guardrail = class_adjusted_mismatch(
            raw_transcript_mismatch,
            content_class,
        )
        bias_primitives = build_bias_primitives(
            title=title,
            description=description,
            transcript=transcript,
            channel_name=channel_name,
            raw_transcript_mismatch=raw_transcript_mismatch,
            adjusted_transcript_mismatch=adjusted_transcript_mismatch,
            content_class=content_class,
            content_class_confidence=content_class_confidence,
            prior_flags=prior_flags,
            channel_risk_mean=float(history_features["channel_risk_mean"]),
            repeat_template_rate=float(history_features["repeat_template_rate"]),
            channel_history_features=history_features,
        )
        prior_frames = infer_bseo_prior_frames(
            title=title,
            description=description,
            transcript=transcript,
            channel_name=channel_name,
            content_class=content_class,
            content_class_confidence=content_class_confidence,
            metrics=bias_primitives,
            prior_flags=prior_flags,
            channel_risk_mean=float(history_features["channel_risk_mean"]),
            repeat_template_rate=float(history_features["repeat_template_rate"]),
            channel_history_features=history_features,
            thumbnail_text_density=round(0.18 + float(score_snapshot.get("risk_score", 0.0) or 0.0) * 0.55, 4),
            thumbnail_shock_indicator=round(0.1 + float(score_snapshot.get("risk_score", 0.0) or 0.0) * 0.62, 4),
        )
        history_features["music_likelihood"] = float(taxonomy["music_likelihood"])
        history_features["content_class_confidence"] = content_class_confidence
        risk_seed = float(
            score_snapshot.get("calibrated_score", score_snapshot.get("risk_score", 0.0)) or 0.0
        )
        mismatch_seed = float(score_snapshot.get("risk_score", raw_transcript_mismatch) or raw_transcript_mismatch)
        feedback_id = str(gold_row.get("feedback_id", "")).strip() or "operator-feedback"
        thumbnail_path = _write_thumbnail_signal(build_id=build_id, feedback_id=feedback_id, risk_seed=risk_seed)
        record = validate_dataset_record(
            {
                "item_id": str(gold_row.get("item_id", "")).strip(),
                "platform": "youtube",
                "source_run_id": run_id,
                "source_url": str(gold_row.get("item_id", "")).strip(),
                "collected_at": str(
                    observation.get("provenance", {}).get("observed_at")
                    or gold_row.get("decided_at")
                    or utc_now()
                ),
                "title": title,
                "channel_name": channel_name,
                "thumbnail_path": thumbnail_path,
                "description": description,
                "tags": [],
                "hashtags": [],
                "transcript_excerpt": transcript or None,
                "metadata": {
                    "upload_time": metadata.get("upload_time"),
                    "duration_seconds": metadata.get("duration_seconds") or 0,
                    "view_count": metadata.get("view_count") or 0,
                    "like_count": metadata.get("like_count") or 0,
                    "channel_prior_flags": prior_flags,
                    "template_cluster": "operator-feedback",
                    "risk_seed": risk_seed,
                    "mismatch_seed": mismatch_seed,
                    "duplicate_of": None,
                    "transcript_path": None,
                    "thumbnail_source_url": observation.get("thumbnail_ref"),
                    "thumbnail_artifact_kind": "signal-json",
                    "acquisition_status": "operator-feedback-ingested",
                    "weak_label_score": risk_seed,
                    "uncertainty_bucket": (
                        "high"
                        if float(score_snapshot.get("uncertainty", 0.0) or 0.0) >= 0.45
                        else "medium"
                    ),
                    "source_trust_flag": "supplemental-adjudicated",
                },
                "history": {
                    "channel_history_features": history_features,
                    "prior_flags": prior_flags,
                },
                "features": {
                    "image_fingerprint": hashlib.sha1(
                        f"{feedback_id}:{observation.get('thumbnail_ref')}".encode("utf-8")
                    ).hexdigest(),
                    "text_fingerprint": hashlib.sha1(
                        f"{title.lower()}::{channel_name.lower()}".encode("utf-8")
                    ).hexdigest(),
                    "language": "en",
                    "template_cluster": "operator-feedback",
                    "title_length": len(title),
                    "uppercase_ratio": uppercase_ratio(title),
                    "sensational_count": sensational_count,
                    "mismatch_score": round(mismatch_seed, 4),
                    "transcript_title_overlap": transcript_overlap(title, transcript),
                    "raw_transcript_mismatch_score": raw_transcript_mismatch,
                    "transcript_mismatch_score": adjusted_transcript_mismatch,
                    "content_class": content_class,
                    "content_class_confidence": content_class_confidence,
                    "content_class_scores": taxonomy["content_class_scores"],
                    "taxonomy_guardrail": guardrail,
                    "bias_primitives": bias_primitives,
                    "dominant_bias_risk": dominant_bias_name(bias_primitives),
                    "bseo_positive_contexts": list(prior_frames["positive_contexts"]),
                    "bseo_negative_contexts": list(prior_frames["negative_contexts"]),
                    "bseo_parameter_frames": dict(prior_frames["parameter_frames"]),
                    "thumbnail_brightness": 0.45,
                    "thumbnail_saturation": round(0.2 + risk_seed * 0.65, 4),
                    "thumbnail_contrast": round(0.24 + risk_seed * 0.5, 4),
                    "thumbnail_text_density": round(0.18 + risk_seed * 0.55, 4),
                    "thumbnail_face_emphasis": round(0.12 + risk_seed * 0.38, 4),
                    "thumbnail_shock_indicator": round(0.1 + risk_seed * 0.62, 4),
                    "thumbnail_entropy": 0.4,
                    "thumbnail_aspect_ratio": round((16 / 9) / 2.5, 4),
                    "thumbnail_artifact_kind": "signal-json",
                    "thumbnail_byte_size": 128.0,
                },
                "labels": dict(gold_row.get("labels", {})),
                "provenance": {
                    "transform_version": "operator-feedback-ingestion-v1",
                    "dataset_build_id": "unbuilt",
                    "split": "unassigned",
                    "origin": "supplemental-adjudicated",
                    "operator_feedback_manifest_path": manifest.get("source_manifest_path")
                    or relative_path(_latest_operator_feedback_manifest_path()),
                    "operator_adjudication_path": adjudication_payload.get("adjudication_path")
                    or relative_path(_latest_operator_adjudication_path()),
                    "operator_gold_path": adjudication_payload.get("gold_path")
                    or relative_path(_latest_operator_gold_path()),
                    "feedback_id": feedback_id,
                    "observation_id": observation.get("observation_id"),
                    "operator_id": provenance.get("operator_id"),
                },
                "annotator_notes": [
                    (
                        f"Operator supplemental gold ingested from feedback_id={feedback_id} "
                        f"resolution={gold_row.get('resolution')} origin=creator-operator-feedback."
                    )
                ],
            }
        ).model_dump()
        record["features"]["title_length"] = max(record["features"]["title_length"], int(distilled_features.get("title_token_count", 0)))
        records.append(record)

    record_path = repo_root() / "datasets" / "interim" / "operator_feedback" / f"{build_id}.jsonl"
    if records:
        write_jsonl(record_path, records)
    manifest_payload = {
        "build_id": build_id,
        "run_id": run_id,
        "generated_at": utc_now(),
        "operator_id": manifest.get("operator_id"),
        "source_manifest_path": relative_path(_latest_operator_feedback_manifest_path())
        if _latest_operator_feedback_manifest_path().exists()
        else None,
        "source_adjudication_path": relative_path(_latest_operator_adjudication_path())
        if _latest_operator_adjudication_path().exists()
        else None,
        "source_gold_path": relative_path(_latest_operator_gold_path())
        if _latest_operator_gold_path().exists()
        else None,
        "record_path": relative_path(record_path) if records else None,
        "ingested_count": len(records),
        "skipped_count": len(skipped),
        "skipped_rows": skipped,
        "feedback_ids": [str(row.get("feedback_id")) for row in gold_rows],
    }
    write_json(
        repo_root() / "datasets" / "manifests" / "operator_feedback" / f"{build_id}-ingestion.json",
        manifest_payload,
    )
    return records, manifest_payload
