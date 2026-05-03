from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from truthlens_data_pipeline.paths import read_json, read_jsonl, relative_path, repo_root, write_json
from truthlens_dataset_governance import load_latest_build_manifest
from truthlens_model_serving import load_model_info
from truthlens_policy_engine import score_item
from truthlens_shared_schemas.contracts import ChannelInfo, ItemMetadata, RuntimeContext, ScoreItemRequest

from .metrics import compute_binary_metrics, confusion_counts, expected_calibration_error


TARGET_LABELS = (
    "clickbait",
    "misleading_thumbnail",
    "misleading_title",
    "fearbait",
    "ai_mass_spam",
)
ROUTE_NAMES = (
    "minimal_creative",
    "informational_consistency",
    "high_risk_factual",
    "ambiguous_escalated",
)
CONTENT_CLASS_NAMES = (
    "music",
    "art",
    "satire",
    "gaming",
    "tutorial",
    "documentary",
    "news",
    "politics",
    "health",
    "finance",
    "commentary",
    "promo",
    "unknown",
)
CREATIVE_CLASSES = {"music", "art", "satire", "gaming"}
HIGH_RISK_CLASSES = {"news", "politics", "health", "finance", "documentary", "commentary", "promo", "unknown"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _target(record: dict[str, Any]) -> int:
    return int(any(bool(record.get("labels", {}).get(name, False)) for name in TARGET_LABELS))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _score_request_from_record(record: dict[str, Any]) -> ScoreItemRequest:
    thumbnail_path = repo_root() / str(record.get("thumbnail_path", ""))
    thumbnail_ref = str(thumbnail_path) if thumbnail_path.exists() else None
    metadata = dict(record.get("metadata", {}))
    history = dict(record.get("history", {}))
    history_features = dict(history.get("channel_history_features", {}))
    return ScoreItemRequest(
        item_id=str(record["item_id"]),
        title=str(record["title"]),
        thumbnail_ref=thumbnail_ref,
        description_snapshot=str(record.get("description", "") or "") or None,
        transcript_excerpt=str(record.get("transcript_excerpt", "") or "") or None,
        metadata=ItemMetadata(
            upload_time=str(metadata.get("upload_time", "") or "") or None,
            duration_seconds=metadata.get("duration_seconds"),
            view_count=metadata.get("view_count"),
            like_count=metadata.get("like_count"),
        ),
        channel=ChannelInfo(
            channel_name=str(record.get("channel_name", "Unknown channel")),
            prior_flags=int(history.get("prior_flags", 0)),
            channel_history_features=history_features,
        ),
        runtime_context=RuntimeContext(
            surface="trainer",
            review_requested=False,
            source_provenance=str(record.get("source_url", "") or "") or None,
        ),
    )


def _model_decision_threshold(model_info: dict[str, Any]) -> float:
    threshold = _safe_float(model_info.get("decision_threshold"), 0.5)
    return max(0.0, min(threshold, 1.0))


def _metric_block(rows: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    if not rows:
        return {
            "sample_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "metrics": {},
            "calibration_error": None,
            "confusion_matrix": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "average_risk_score": None,
            "average_truth_score_10": None,
            "recommended_action_distribution": {},
            "runtime_route_distribution": {},
            "guard_distribution": {},
            "mismatch_pressure_distribution": {},
        }
    labels = [int(row["label"]) for row in rows]
    scores = [float(row["risk_score"]) for row in rows]
    actions = Counter(str(row["recommended_action"]) for row in rows)
    routes = Counter(str(row["runtime_route"]) for row in rows)
    guards = Counter(str(row["adversarial_guard"]) for row in rows)
    pressures = Counter(str(row["mismatch_pressure"]) for row in rows)
    return {
        "sample_count": len(rows),
        "positive_count": sum(labels),
        "negative_count": len(labels) - sum(labels),
        "metrics": compute_binary_metrics(labels, scores, threshold=threshold),
        "calibration_error": expected_calibration_error(labels, scores),
        "confusion_matrix": confusion_counts(labels, scores, threshold=threshold),
        "average_risk_score": round(sum(scores) / len(scores), 4),
        "average_truth_score_10": round(sum(float(row["truth_score_10"]) for row in rows) / len(rows), 4),
        "recommended_action_distribution": dict(sorted(actions.items())),
        "runtime_route_distribution": dict(sorted(routes.items())),
        "guard_distribution": dict(sorted(guards.items())),
        "mismatch_pressure_distribution": dict(sorted(pressures.items())),
    }


def _segment_metrics(
    rows: list[dict[str, Any]],
    *,
    key: str,
    expected_keys: Iterable[str],
    threshold: float,
) -> dict[str, Any]:
    segments: dict[str, list[dict[str, Any]]] = {name: [] for name in expected_keys}
    for row in rows:
        segments.setdefault(str(row.get(key, "unknown")), []).append(row)
    return {
        name: _metric_block(segment_rows, threshold=threshold)
        for name, segment_rows in sorted(segments.items())
        if segment_rows or name in expected_keys
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _architecture_checks(rows: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    predicted_positive = [row for row in rows if float(row["risk_score"]) >= threshold]
    creative_negative = [
        row
        for row in rows
        if int(row["label"]) == 0
        and (str(row["content_class"]) in CREATIVE_CLASSES or str(row["runtime_route"]) == "minimal_creative")
    ]
    creative_fp = [row for row in creative_negative if float(row["risk_score"]) >= threshold]
    camouflage_positive = [
        row
        for row in rows
        if int(row["label"]) == 1
        and str(row["content_class"]) in CREATIVE_CLASSES
        and str(row["adversarial_guard"]) == "triggered"
    ]
    camouflage_fn = [row for row in camouflage_positive if float(row["risk_score"]) < threshold]
    high_risk_rows = [
        row
        for row in rows
        if str(row["runtime_route"]) == "high_risk_factual" or str(row["content_class"]) in HIGH_RISK_CLASSES
    ]
    final_differs = [
        row
        for row in rows
        if str(row["threshold_action"]) != str(row["recommended_action"])
    ]
    bseo_live = [row for row in rows if str(row["decisive_layer"]) == "bseo-live"]
    minimal_clean = [
        row
        for row in rows
        if str(row["runtime_route"]) == "minimal_creative" and str(row["adversarial_guard"]) == "clean"
    ]
    action_rank = {"none": 0, "badge": 1, "blur": 2, "ask-report": 3, "hide": 4}
    active_actions = [row for row in rows if action_rank.get(str(row["recommended_action"]), 0) > 0]
    truth_scores = [float(row["truth_score_10"]) for row in rows]
    risks = [float(row["risk_score"]) for row in rows]
    score_contract_consistent = all(0.0 <= risk <= 1.0 for risk in risks) and all(
        0.0 <= truth <= 10.0 for truth in truth_scores
    )
    return {
        "score_contract": {
            "raw_risk_high_is_worse": True,
            "ui_truth_score_high_is_better": True,
            "truth_score_formula": "round((1.0 - risk_score) * 10.0, 1)",
            "reranking_direction_expected": "higher UI truth score promotes; higher raw risk demotes",
            "bounded_outputs": score_contract_consistent,
        },
        "predicted_positive_count": len(predicted_positive),
        "active_recommended_action_count": len(active_actions),
        "creative_false_positive_rate": _rate(len(creative_fp), len(creative_negative)),
        "creative_negative_count": len(creative_negative),
        "creative_false_positive_count": len(creative_fp),
        "deceptive_factual_camouflage_false_negative_rate": _rate(
            len(camouflage_fn),
            len(camouflage_positive),
        ),
        "deceptive_factual_camouflage_positive_count": len(camouflage_positive),
        "deceptive_factual_camouflage_false_negative_count": len(camouflage_fn),
        "high_risk_factual": _metric_block(high_risk_rows, threshold=threshold),
        "bseo_override_frequency": _rate(len(final_differs), len(rows)),
        "bseo_live_decision_frequency": _rate(len(bseo_live), len(rows)),
        "minimal_creative_clean": _metric_block(minimal_clean, threshold=threshold),
    }


def _compact_row(record: dict[str, Any], split_name: str, threshold: float) -> dict[str, Any]:
    result = score_item(_score_request_from_record(record))
    route = result.semantic_evidence_route.model_dump(mode="json")
    basis = result.action_decision_basis
    risk_score = float(result.risk_score)
    return {
        "item_id": str(record["item_id"]),
        "split": split_name,
        "label": _target(record),
        "risk_score": round(risk_score, 4),
        "truth_score_10": round((1.0 - risk_score) * 10.0, 1),
        "predicted_positive": risk_score >= threshold,
        "confidence": float(result.confidence),
        "uncertainty": float(result.uncertainty),
        "content_class": _enum_value(result.content_class),
        "content_class_confidence": float(result.content_class_confidence),
        "runtime_route": str(route.get("runtime_route", "ambiguous_escalated")),
        "adversarial_guard": str(route.get("adversarial_guard", "triggered")),
        "mismatch_pressure": str(route.get("mismatch_pressure", "normal")),
        "learning_capture_plan": str(route.get("learning_capture_plan", "full_multimodal_capture")),
        "recommended_action": _enum_value(result.recommended_action),
        "threshold_action": _enum_value(basis.threshold_action),
        "decisive_layer": str(basis.decisive_layer),
        "policy_mode": str(result.policy_mode),
        "resolved_policy_mode": str(result.resolved_policy_mode),
        "verification_status": str(result.verification.status),
        "verification_review_recommended": bool(result.verification.review_recommended),
    }


def _data_decision(manifest: dict[str, Any]) -> dict[str, Any]:
    source_records = list(manifest.get("sources", {}).get("source_manifest", {}).get("records", []))
    synthetic_count = sum(
        1
        for record in source_records
        if str(record.get("access_method", "")).strip() == "synthetic-bootstrap"
    )
    return {
        "used_for_global_benchmark_truth": [
            manifest.get("artifacts", {}).get("validation"),
            manifest.get("artifacts", {}).get("test"),
        ],
        "used_for_training_truth": [],
        "operator_feedback_policy": (
            "Only creator/operator rows already included through the governed build manifest are part "
            "of this benchmark truth."
        ),
        "excluded_from_global_benchmark_truth": [
            "artifacts/reports/feedback_events.jsonl",
            "artifacts/reports/score_events.jsonl",
            "artifacts/reports/browser_observations.jsonl",
            "local runtime SQLite/Postgres event stores",
        ],
        "exclusion_reason": (
            "Ordinary local/public-user feedback remains supplemental runtime evidence until a controlled "
            "adjudication and split-governance path promotes it."
        ),
        "raw_media_policy": "No raw media is copied into this artifact; rows retain compact route/context metrics only.",
        "source_access_method_counts": {
            "synthetic_bootstrap": synthetic_count,
            "source_manifest_records": len(source_records),
        },
    }


def build_semantic_routing_evaluation(
    *,
    manifest: dict[str, Any] | None = None,
    evaluation_label: str = "current-runtime",
    split_names: tuple[str, ...] = ("validation", "test"),
) -> dict[str, Any]:
    resolved_manifest = manifest or load_latest_build_manifest()
    model_info = load_model_info()
    threshold = _model_decision_threshold(model_info)
    rows: list[dict[str, Any]] = []
    split_payloads: dict[str, Any] = {}
    for split_name in split_names:
        records = read_jsonl(repo_root() / str(resolved_manifest["artifacts"][split_name]))
        split_rows = [_compact_row(record, split_name, threshold) for record in records]
        rows.extend(split_rows)
        split_payloads[split_name] = _metric_block(split_rows, threshold=threshold)
    return {
        "artifact_type": "semantic-routing-evaluation",
        "schema_version": "2026-05-03",
        "generated_at": _utc_now(),
        "evaluation_label": evaluation_label,
        "build_id": resolved_manifest["build_id"],
        "model_version": model_info.get("model_version"),
        "model_build_id": model_info.get("build_id"),
        "decision_threshold": threshold,
        "source_splits": list(split_names),
        "source_artifacts": {
            split_name: resolved_manifest["artifacts"][split_name]
            for split_name in split_names
        },
        "data_decision": _data_decision(resolved_manifest),
        "sample_count": len(rows),
        "label_distribution": dict(sorted(Counter(int(row["label"]) for row in rows).items())),
        "splits": split_payloads,
        "overall": _metric_block(rows, threshold=threshold),
        "route_segments": _segment_metrics(
            rows,
            key="runtime_route",
            expected_keys=ROUTE_NAMES,
            threshold=threshold,
        ),
        "content_class_segments": _segment_metrics(
            rows,
            key="content_class",
            expected_keys=CONTENT_CLASS_NAMES,
            threshold=threshold,
        ),
        "architecture_checks": _architecture_checks(rows, threshold=threshold),
        "compact_rows": rows,
    }


def write_semantic_routing_evaluation(
    *,
    manifest: dict[str, Any] | None = None,
    evaluation_label: str = "current-runtime",
    output_path: Path | None = None,
    split_names: tuple[str, ...] = ("validation", "test"),
) -> dict[str, Any]:
    payload = build_semantic_routing_evaluation(
        manifest=manifest,
        evaluation_label=evaluation_label,
        split_names=split_names,
    )
    path = output_path or (
        repo_root()
        / "artifacts"
        / "eval_runs"
        / f"{payload['build_id']}-semantic-routing-eval.json"
    )
    write_json(path, payload)
    return payload


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def build_calibration_decision(
    *,
    manifest: dict[str, Any] | None = None,
    semantic_eval: dict[str, Any] | None = None,
    simulation: dict[str, Any] | None = None,
    decision_label: str = "post-training-runtime",
) -> dict[str, Any]:
    resolved_manifest = manifest or load_latest_build_manifest()
    root = repo_root()
    build_id = str(resolved_manifest["build_id"])
    eval_report = _read_json_if_exists(root / "artifacts" / "eval_runs" / f"{build_id}.json")
    resolved_semantic_eval = semantic_eval or _read_json_if_exists(
        root / "artifacts" / "eval_runs" / f"{build_id}-semantic-routing-eval.json"
    )
    resolved_simulation = simulation or _read_json_if_exists(
        root / "artifacts" / "eval_runs" / f"{build_id}-simulation.json"
    )
    bseo_report = _read_json_if_exists(root / "artifacts" / "eval_runs" / f"{build_id}-bseo-report.json")
    sample_count = _safe_int(resolved_semantic_eval.get("sample_count"), _safe_int(eval_report.get("sample_count")))
    label_distribution = dict(resolved_semantic_eval.get("label_distribution", {}))
    has_both_labels = len({str(key) for key, value in label_distribution.items() if _safe_int(value) > 0}) >= 2
    source_counts = dict(resolved_semantic_eval.get("data_decision", {}).get("source_access_method_counts", {}))
    synthetic_records = _safe_int(source_counts.get("synthetic_bootstrap"))
    source_records = _safe_int(source_counts.get("source_manifest_records"))
    threshold_sweep = list(resolved_simulation.get("threshold_sweep", []))
    bseo_search = dict(resolved_simulation.get("bseo_search", {}))
    best_theta = dict(bseo_report.get("best_theta") or bseo_search.get("best_theta") or {})
    recommended_thresholds = dict(
        bseo_report.get("recommended_thresholds")
        or resolved_simulation.get("recommended_thresholds")
        or {}
    )
    data_too_small = sample_count < 30
    synthetic_heavy = source_records > 0 and synthetic_records / max(source_records, 1) >= 0.75
    no_tune = data_too_small or not has_both_labels or not threshold_sweep
    return {
        "artifact_type": "calibration-hyperparameter-decision",
        "schema_version": "2026-05-03",
        "generated_at": _utc_now(),
        "decision_label": decision_label,
        "build_id": build_id,
        "model_version": load_model_info().get("model_version"),
        "decision": "no-tune" if no_tune else "controlled-calibration-recorded",
        "promotion_decision": "requires-metric-comparison-before-model-promotion",
        "data_assessment": {
            "sample_count": sample_count,
            "label_distribution": label_distribution,
            "has_both_labels": has_both_labels,
            "synthetic_bootstrap_source_records": synthetic_records,
            "source_manifest_records": source_records,
            "synthetic_heavy": synthetic_heavy,
            "too_small_for_tuning": data_too_small,
        },
        "parameters": {
            "threshold_calibration": {
                "status": "evaluated" if threshold_sweep else "not-evaluated",
                "changed": bool(recommended_thresholds and not no_tune),
                "recommended_thresholds": recommended_thresholds,
                "reason": "Existing threshold sweep and BSEO search artifacts provide bounded calibration evidence.",
            },
            "class_conditioned_mismatch_weights": {
                "status": "evaluated" if best_theta else "not-evaluated",
                "changed": bool(best_theta.get("mismatch_weight_by_class") and not no_tune),
                "values": dict(best_theta.get("mismatch_weight_by_class", {})),
            },
            "bseo_pressure_multipliers": {
                "status": "evaluated",
                "changed": False,
                "reason": "BSEO remains downstream; this workpack measures route pressure but does not alter policy code.",
            },
            "creative_discount_bounds": {
                "status": "evaluated",
                "changed": False,
                "reason": "Creative discount bounds remain governed by AdaptiveSemanticEvidenceRouter and BSEO guard state.",
            },
            "ambiguous_escalation_thresholds": {
                "status": "evaluated",
                "changed": False,
                "reason": "Escalation thresholds are measured route outcomes, not retuned on this small repo benchmark alone.",
            },
            "high_risk_factual_strictness": {
                "status": "evaluated",
                "changed": False,
                "reason": "High-risk factual strictness remains enforced by route and BSEO policy; no router code change.",
            },
            "score_calibration": {
                "status": "evaluated" if eval_report else "not-evaluated",
                "changed": False,
                "calibration_error": eval_report.get("calibration_error"),
                "validation_calibration_error": eval_report.get("validation_calibration_error"),
            },
        },
        "changed": [
            "threshold artifacts generated by the existing bounded simulation pipeline"
            if recommended_thresholds and not no_tune
            else "no runtime threshold tuning accepted"
        ],
        "not_changed": [
            "AdaptiveSemanticEvidenceRouter rules",
            "BSEO downstream policy code",
            "creative discount bounds",
            "ambiguous escalation thresholds",
            "high-risk factual strictness rules",
            "training labels or split lineage",
        ],
        "reason": (
            "Dataset is too small or not label-diverse enough for tuning."
            if no_tune
            else "Controlled calibration artifacts were generated from governed validation/test records; "
            "route context is diagnostic and not used as a label."
        ),
        "input_artifacts": {
            "semantic_routing_eval": f"artifacts/eval_runs/{build_id}-semantic-routing-eval.json",
            "simulation": f"artifacts/eval_runs/{build_id}-simulation.json",
            "model_eval": f"artifacts/eval_runs/{build_id}.json",
            "bseo_report": f"artifacts/eval_runs/{build_id}-bseo-report.json",
        },
    }


def write_calibration_decision(
    *,
    manifest: dict[str, Any] | None = None,
    semantic_eval: dict[str, Any] | None = None,
    simulation: dict[str, Any] | None = None,
    decision_label: str = "post-training-runtime",
    output_path: Path | None = None,
) -> dict[str, Any]:
    payload = build_calibration_decision(
        manifest=manifest,
        semantic_eval=semantic_eval,
        simulation=simulation,
        decision_label=decision_label,
    )
    path = output_path or (
        repo_root()
        / "artifacts"
        / "eval_runs"
        / f"{payload['build_id']}-calibration-decision.json"
    )
    write_json(path, payload)
    return payload


def write_no_retrain_decision(
    *,
    build_id: str,
    reason: str,
    output_path: Path | None = None,
) -> dict[str, Any]:
    path = output_path or repo_root() / "artifacts" / "eval_runs" / f"{build_id}-no-retrain-decision.json"
    payload = {
        "artifact_type": "no-retrain-decision",
        "schema_version": "2026-05-03",
        "generated_at": _utc_now(),
        "build_id": build_id,
        "reason": reason,
        "artifact_path": relative_path(path),
    }
    write_json(path, payload)
    return payload


def write_no_promotion_decision(
    *,
    build_id: str,
    reason: str,
    output_path: Path | None = None,
) -> dict[str, Any]:
    path = output_path or repo_root() / "artifacts" / "eval_runs" / f"{build_id}-no-promotion-decision.json"
    payload = {
        "artifact_type": "no-promotion-decision",
        "schema_version": "2026-05-03",
        "generated_at": _utc_now(),
        "build_id": build_id,
        "reason": reason,
        "artifact_path": relative_path(path),
    }
    write_json(path, payload)
    return payload


def main() -> None:
    manifest = load_latest_build_manifest()
    path = (
        repo_root()
        / "artifacts"
        / "eval_runs"
        / f"{manifest['build_id']}-semantic-routing-baseline-eval.json"
    )
    write_semantic_routing_evaluation(
        manifest=manifest,
        evaluation_label="baseline-current-latest",
        output_path=path,
    )
    print(relative_path(path))


if __name__ == "__main__":
    main()
