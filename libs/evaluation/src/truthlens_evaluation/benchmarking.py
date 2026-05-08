from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from truthlens_data_pipeline.paths import ensure_dir, read_json, read_jsonl, repo_root, write_json
from truthlens_evaluation.runtime_governance import persist_runtime_governance_summary
from truthlens_model_serving import summarize_browser_observations, summarize_feedback_events


ASSET_FILENAMES = (
    "train_validation_eval_overview.svg",
    "per_head_metrics.svg",
    "calibration_error.svg",
    "confusion_matrix_eval.svg",
    "training_loss_curve.svg",
    "training_accuracy_curve.svg",
    "threshold_sweep.svg",
    "drift_summary.svg",
    "policy_mode_comparison.svg",
    "runtime_governance.svg",
    "observation_feedback_intake.svg",
    "benchmark_provenance.svg",
    "semantic_route_distribution.svg",
    "semantic_route_performance.svg",
    "content_class_route_performance.svg",
    "recommended_action_distribution.svg",
    "semantic_route_before_after.svg",
    "creative_fpr_diagnostic.svg",
    "bseo_bias_profile.svg",
    "mutation_bias_atlas.svg",
    "lineage_overview.svg",
)

INTERACTIVE_FILENAMES = (
    "metrics_dashboard.html",
    "threshold_explorer.html",
    "bseo_policy_dashboard.html",
    "mutation_atlas.html",
    "runtime_governance_dashboard.html",
    "semantic_routing_dashboard.html",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _read_jsonl_if_exists(path: Path | None) -> list[dict[str, Any]] | None:
    if path is None or not path.exists():
        return None
    rows = read_jsonl(path)
    return [row for row in rows if isinstance(row, dict)]


def _find_latest_json(directory: Path, name_suffix: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(
        [path for path in directory.glob(f"*{name_suffix}") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _find_latest_eval_report(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(
        [
            path
            for path in directory.glob("*.json")
            if path.is_file()
            and not path.name.endswith("-simulation.json")
            and not path.name.endswith("-bseo-report.json")
            and not path.name.endswith("-mutation-bias-atlas.json")
            and not path.name.endswith("-bseo-lineage.json")
            and not path.name.endswith("-training-history.json")
            and not path.name.endswith("-semantic-routing-eval.json")
            and not path.name.endswith("-creative-fpr-before-eval.json")
            and not path.name.endswith("-creative-fpr-diagnostic.json")
            and not path.name.endswith("-calibration-decision.json")
            and not path.name.endswith("-no-retrain-decision.json")
            and not path.name.endswith("-no-promotion-decision.json")
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _relative(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(repo_root()).as_posix()
    except ValueError:
        return path.as_posix()


def _artifact_paths() -> dict[str, Path | None]:
    root = repo_root()
    model_info_path = root / "artifacts" / "trained_models" / "latest" / "model_info.json"
    model_info = _read_json_if_exists(model_info_path)
    build_id = str((model_info or {}).get("build_id", "")).strip()
    eval_dir = root / "artifacts" / "eval_runs"
    drift_dir = root / "artifacts" / "drift_reports"
    thresholds_dir = root / "configs" / "thresholds"
    supplemental_candidate_dir = root / "datasets" / "labels" / "supplemental_candidates"
    supplemental_adjudication_dir = root / "datasets" / "labels" / "supplemental_adjudication"
    supplemental_gold_dir = root / "datasets" / "labels" / "supplemental_gold"
    operator_feedback_dir = root / "datasets" / "manifests" / "operator_feedback"
    operator_adjudication_dir = operator_feedback_dir / "adjudication"
    operator_gold_dir = operator_feedback_dir / "gold"
    build_manifest_path = root / "datasets" / "manifests" / "builds" / "latest.json"

    eval_report_path = (
        eval_dir / f"{build_id}.json"
        if build_id and (eval_dir / f"{build_id}.json").exists()
        else _find_latest_eval_report(eval_dir)
    )
    simulation_path = (
        eval_dir / f"{build_id}-simulation.json"
        if build_id and (eval_dir / f"{build_id}-simulation.json").exists()
        else _find_latest_json(eval_dir, "-simulation.json")
    )
    training_history_path = (
        eval_dir / f"{build_id}-training-history.json"
        if build_id and (eval_dir / f"{build_id}-training-history.json").exists()
        else _find_latest_json(eval_dir, "-training-history.json")
    )
    semantic_routing_eval_path = (
        eval_dir / f"{build_id}-semantic-routing-eval.json"
        if build_id and (eval_dir / f"{build_id}-semantic-routing-eval.json").exists()
        else _find_latest_json(eval_dir, "-semantic-routing-eval.json")
    )
    semantic_routing_baseline_eval_path = (
        eval_dir / f"{build_id}-semantic-routing-baseline-eval.json"
        if build_id and (eval_dir / f"{build_id}-semantic-routing-baseline-eval.json").exists()
        else _find_latest_json(eval_dir, "-semantic-routing-baseline-eval.json")
    )
    calibration_decision_path = (
        eval_dir / f"{build_id}-calibration-decision.json"
        if build_id and (eval_dir / f"{build_id}-calibration-decision.json").exists()
        else _find_latest_json(eval_dir, "-calibration-decision.json")
    )
    creative_fpr_before_eval_path = (
        eval_dir / f"{build_id}-creative-fpr-before-eval.json"
        if build_id and (eval_dir / f"{build_id}-creative-fpr-before-eval.json").exists()
        else _find_latest_json(eval_dir, "-creative-fpr-before-eval.json")
    )
    creative_fpr_diagnostic_path = (
        eval_dir / f"{build_id}-creative-fpr-diagnostic.json"
        if build_id and (eval_dir / f"{build_id}-creative-fpr-diagnostic.json").exists()
        else _find_latest_json(eval_dir, "-creative-fpr-diagnostic.json")
    )
    no_retrain_decision_path = (
        eval_dir / f"{build_id}-no-retrain-decision.json"
        if build_id and (eval_dir / f"{build_id}-no-retrain-decision.json").exists()
        else _find_latest_json(eval_dir, "-no-retrain-decision.json")
    )
    no_promotion_decision_path = (
        eval_dir / f"{build_id}-no-promotion-decision.json"
        if build_id and (eval_dir / f"{build_id}-no-promotion-decision.json").exists()
        else _find_latest_json(eval_dir, "-no-promotion-decision.json")
    )
    bseo_report_path = (
        eval_dir / f"{build_id}-bseo-report.json"
        if build_id and (eval_dir / f"{build_id}-bseo-report.json").exists()
        else _find_latest_json(eval_dir, "-bseo-report.json")
    )
    mutation_atlas_path = (
        eval_dir / f"{build_id}-mutation-bias-atlas.json"
        if build_id and (eval_dir / f"{build_id}-mutation-bias-atlas.json").exists()
        else _find_latest_json(eval_dir, "-mutation-bias-atlas.json")
    )
    lineage_path = (
        eval_dir / f"{build_id}-bseo-lineage.json"
        if build_id and (eval_dir / f"{build_id}-bseo-lineage.json").exists()
        else _find_latest_json(eval_dir, "-bseo-lineage.json")
    )
    drift_path = (
        drift_dir / f"{build_id}.json"
        if build_id and (drift_dir / f"{build_id}.json").exists()
        else _find_latest_json(drift_dir, ".json")
    )
    runtime_policy_path = thresholds_dir / "runtime-policy.json"
    threshold_path = thresholds_dir / "default.json"
    bseo_policy_path = thresholds_dir / "bseo-policy.json"
    runtime_governance_path = root / "artifacts" / "reports" / "runtime-governance-latest.json"
    operator_feedback_manifest_path = operator_feedback_dir / "latest.json"
    operator_feedback_manifest = _read_json_if_exists(operator_feedback_manifest_path)
    operator_run_id = str((operator_feedback_manifest or {}).get("run_id", "")).strip()
    operator_adjudication_path = (
        operator_adjudication_dir / f"{operator_run_id}.json" if operator_run_id else None
    )
    operator_gold_path = operator_gold_dir / f"{operator_run_id}.jsonl" if operator_run_id else None
    operator_ingestion_manifest_path = (
        operator_feedback_dir / f"{build_id}-ingestion.json" if build_id else None
    )
    return {
        "model_info": model_info_path if model_info_path.exists() else None,
        "eval_report": eval_report_path,
        "simulation": simulation_path,
        "training_history": training_history_path,
        "semantic_routing_eval": semantic_routing_eval_path,
        "semantic_routing_baseline_eval": semantic_routing_baseline_eval_path,
        "calibration_decision": calibration_decision_path,
        "creative_fpr_before_eval": creative_fpr_before_eval_path,
        "creative_fpr_diagnostic": creative_fpr_diagnostic_path,
        "no_retrain_decision": no_retrain_decision_path,
        "no_promotion_decision": no_promotion_decision_path,
        "bseo_report": bseo_report_path,
        "mutation_atlas": mutation_atlas_path,
        "lineage": lineage_path,
        "drift_report": drift_path,
        "runtime_policy": runtime_policy_path if runtime_policy_path.exists() else None,
        "thresholds": threshold_path if threshold_path.exists() else None,
        "bseo_policy": bseo_policy_path if bseo_policy_path.exists() else None,
        "runtime_governance": runtime_governance_path if runtime_governance_path.exists() else None,
        "supplemental_candidates": _find_latest_json(supplemental_candidate_dir, ".json"),
        "supplemental_adjudication": _find_latest_json(supplemental_adjudication_dir, ".json"),
        "supplemental_gold": _find_latest_json(supplemental_gold_dir, ".jsonl"),
        "operator_feedback_manifest": (
            operator_feedback_manifest_path if operator_feedback_manifest_path.exists() else None
        ),
        "operator_ingestion_manifest": (
            operator_ingestion_manifest_path
            if operator_ingestion_manifest_path is not None and operator_ingestion_manifest_path.exists()
            else _find_latest_json(operator_feedback_dir, "-ingestion.json")
        ),
        "operator_adjudication": (
            operator_adjudication_path
            if operator_adjudication_path is not None and operator_adjudication_path.exists()
            else _find_latest_json(operator_adjudication_dir, ".json")
        ),
        "operator_gold": (
            operator_gold_path
            if operator_gold_path is not None and operator_gold_path.exists()
            else _find_latest_json(operator_gold_dir, ".jsonl")
        ),
        "build_manifest": build_manifest_path if build_manifest_path.exists() else None,
    }


def _is_generated_workspace_artifact(path: Path) -> bool:
    relative_path = _relative(path) or ""
    return relative_path.startswith(("artifacts/eval_runs/", "artifacts/drift_reports/"))


def _publish_curated_artifact_paths(
    paths: dict[str, Path | None],
    output_root: Path,
) -> dict[str, str]:
    public_artifacts_dir = ensure_dir(output_root / "artifacts")
    candidates: list[tuple[Path, Path, str, str]] = []
    replacements: dict[str, str] = {}
    for path in paths.values():
        if path is None or not path.exists() or not _is_generated_workspace_artifact(path):
            continue
        source_relative = _relative(path)
        destination_name = path.name
        if source_relative and source_relative.startswith("artifacts/drift_reports/"):
            destination_name = f"drift-{path.name}"
        destination = public_artifacts_dir / destination_name
        destination_relative = _relative(destination)
        if source_relative and destination_relative:
            candidates.append((path, destination, source_relative, destination_relative))
            replacements[source_relative] = destination_relative

    for path, destination, _, _ in candidates:
        if path.resolve() == destination.resolve():
            continue
        if path.suffix.lower() == ".json":
            payload = _remap_public_artifact_references(read_json(path), replacements)
            write_json(destination, payload)
        else:
            shutil.copy2(path, destination)
    return replacements


def _remap_public_artifact_references(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_remap_public_artifact_references(item, replacements) for item in value]
    if isinstance(value, dict):
        return {
            key: _remap_public_artifact_references(item, replacements)
            for key, item in value.items()
        }
    return value


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


def _sample_count(eval_report: dict[str, Any] | None) -> int | None:
    if eval_report is None:
        return None
    explicit = eval_report.get("sample_count")
    if explicit is not None:
        return _safe_int(explicit)
    confusion = eval_report.get("confusion_matrix")
    if not isinstance(confusion, dict):
        return None
    return sum(_safe_int(confusion.get(key)) for key in ("tp", "tn", "fp", "fn"))


def _artifact_timestamp(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def _is_truthy_bseo_payload(simulation: dict[str, Any] | None) -> bool:
    if simulation is None:
        return False
    bseo = simulation.get("bseo_search")
    return isinstance(bseo, dict) and bool(bseo)


def _summarize_mutation_atlas(atlas: dict[str, Any] | None) -> dict[str, Any]:
    payload = atlas or {}
    clusters = []
    for cluster in payload.get("clusters", []):
        if not isinstance(cluster, dict):
            continue
        clusters.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "size": cluster.get("size"),
                "average_delta_f": cluster.get("average_delta_f"),
                "average_delta_b": cluster.get("average_delta_b"),
                "average_theta_shift": cluster.get("average_theta_shift"),
            }
        )
    return {
        "status": payload.get("status", "missing"),
        "usable_mutations": _safe_int(payload.get("usable_mutations")),
        "clusters": clusters,
    }


def _summarize_lineage(lineage: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = lineage if isinstance(lineage, list) else []
    accepted = sorted(
        [entry for entry in rows if isinstance(entry, dict) and bool(entry.get("accepted"))],
        key=lambda entry: (_safe_int(entry.get("generation")), str(entry.get("candidate_id"))),
    )
    preview = [
        {
            "candidate_id": entry.get("candidate_id"),
            "generation": entry.get("generation"),
            "objective": entry.get("objective"),
            "delta_f": entry.get("delta_f"),
            "delta_b": entry.get("delta_b"),
            "mutation_type": entry.get("mutation_type"),
        }
        for entry in accepted[:16]
    ]
    return {
        "count": len(rows),
        "accepted_count": len(accepted),
        "accepted_preview": preview,
    }


def _summarize_bseo_report(report: dict[str, Any] | None) -> dict[str, Any]:
    payload = report or {}
    performance = dict(payload.get("best_performance", {}))
    return {
        "build_id": payload.get("build_id"),
        "generated_at": payload.get("generated_at"),
        "policy_version": payload.get("policy_version"),
        "best_candidate_id": payload.get("best_candidate_id"),
        "best_objective": payload.get("best_objective"),
        "recommended_thresholds": dict(payload.get("recommended_thresholds", {})),
        "best_performance": {
            "detection_quality": performance.get("detection_quality"),
            "context_sensitivity": performance.get("context_sensitivity"),
            "macro_ece": performance.get("macro_ece"),
            "calibration": performance.get("calibration"),
            "channel_lock_in": performance.get("channel_lock_in"),
            "genre_confusion": performance.get("genre_confusion"),
            "intervention_rate": performance.get("intervention_rate"),
            "benign_false_positive_rate": performance.get("benign_false_positive_rate"),
            "action_counts": dict(performance.get("action_counts", {})),
            "slice_metrics": dict(performance.get("slice_metrics", {})),
        },
    }


def _summarize_bseo_policy_artifact(policy: dict[str, Any] | None) -> dict[str, Any]:
    payload = policy or {}
    bias_signature = dict(payload.get("bias_signature", {}))
    return {
        "policy_version": payload.get("policy_version"),
        "generated_at": payload.get("generated_at"),
        "build_id": payload.get("build_id"),
        "head_spec_version": payload.get("head_spec_version"),
        "architecture_plan_version": payload.get("architecture_plan_version"),
        "recommended_thresholds": dict(payload.get("recommended_thresholds", {})),
        "control_genome": dict(payload.get("control_genome", {})),
        "bias_signature_macro": dict(bias_signature.get("macro", {})),
        "negative_bias_score": bias_signature.get("negative_bias_score"),
        "objective": dict(payload.get("objective", {})),
        "mutation_bias_atlas": _summarize_mutation_atlas(
            dict(payload.get("mutation_bias_atlas", {})) if isinstance(payload.get("mutation_bias_atlas"), dict) else {}
        ),
        "lineage_log_path": payload.get("lineage_log_path"),
        "mutation_bias_atlas_path": payload.get("mutation_bias_atlas_path"),
        "report_path": payload.get("report_path"),
    }


def _summarize_supplemental_intake(
    candidate_batch: dict[str, Any] | None,
    supplemental_adjudication: dict[str, Any] | None,
    supplemental_gold: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    candidate_payload = candidate_batch or {}
    summary = dict(candidate_payload.get("summary", {}))
    adjudication_summary = dict((supplemental_adjudication or {}).get("summary", {}))
    queues = dict(candidate_payload.get("supplemental_candidates", {}))
    all_candidates = [
        candidate
        for queue in queues.values()
        if isinstance(queue, list)
        for candidate in queue
        if isinstance(candidate, dict)
    ]
    tag_counter: dict[str, int] = {}
    collection_scoped_count = 0
    for candidate in all_candidates:
        for tag in candidate.get("selected_tags", []):
            normalized = str(tag).strip()
            if normalized:
                tag_counter[normalized] = tag_counter.get(normalized, 0) + 1
        collection_scope = candidate.get("collection_scope")
        if isinstance(collection_scope, dict) and str(collection_scope.get("scope_type", "single")) != "single":
            collection_scoped_count += 1
    return {
      "candidate_count": _safe_int(summary.get("candidate_count")),
      "feedback_linked_count": _safe_int(summary.get("feedback_linked_count")),
      "observation_linked_count": _safe_int(summary.get("observation_linked_count")),
      "manual_report_linked_count": _safe_int(summary.get("manual_report_linked_count")),
      "split_blocked_count": _safe_int(summary.get("split_blocked_count")),
      "review_queue_count": len(queues.get("review_queue", [])),
      "hard_negative_queue_count": len(queues.get("hard_negative_queue", [])),
      "disagreement_queue_count": len(queues.get("disagreement_queue", [])),
      "adjudicated_count": _safe_int(adjudication_summary.get("saved_count")),
      "confirmed_count": _safe_int(adjudication_summary.get("confirmed_count")),
      "escalation_count": _safe_int(adjudication_summary.get("escalation_count")),
      "supplemental_gold_count": len(supplemental_gold or []),
      "collection_scoped_count": collection_scoped_count,
      "selected_tag_counts": tag_counter,
    }


def _summarize_operator_feedback(
    operator_manifest: dict[str, Any] | None,
    operator_adjudication: dict[str, Any] | None,
    operator_gold: list[dict[str, Any]] | None,
    build_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest_payload = operator_manifest or {}
    adjudication_payload = operator_adjudication or {}
    adjudication_summary = dict(adjudication_payload.get("summary", {}))
    build_operator = dict((build_manifest or {}).get("operator_feedback", {}))
    return {
        "candidate_count": _safe_int(manifest_payload.get("selected_count")),
        "adjudicated_count": _safe_int(adjudication_summary.get("saved_count")),
        "confirmed_count": _safe_int(adjudication_summary.get("confirmed_count")),
        "confirmed_risk_count": _safe_int(adjudication_summary.get("confirmed_risk_count")),
        "confirmed_benign_count": _safe_int(adjudication_summary.get("confirmed_benign_count")),
        "gold_count": len(operator_gold or []),
        "ingested_count": _safe_int(build_operator.get("ingested_count")),
        "operator_id": manifest_payload.get("operator_id"),
        "action_counts": dict(manifest_payload.get("selected_action_counts", {})),
        "selected_channels": dict(manifest_payload.get("selected_channels", {})),
    }


def _summarize_global_benchmark_truth(
    build_manifest: dict[str, Any] | None,
    eval_report: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = build_manifest or {}
    counts = dict(payload.get("counts", {}))
    return {
        "build_id": payload.get("build_id"),
        "train_count": _safe_int(counts.get("train")),
        "validation_count": _safe_int(counts.get("validation")),
        "test_count": _safe_int(counts.get("test")),
        "total_records": sum(_safe_int(value) for value in counts.values()),
        "eval_sample_count": _sample_count(eval_report) or 0,
    }


def _subtract_action_counts(
    total_action_counts: dict[str, Any],
    creator_action_counts: dict[str, Any],
) -> dict[str, int]:
    remaining: dict[str, int] = {}
    for key in sorted(set(total_action_counts) | set(creator_action_counts)):
        value = _safe_int(total_action_counts.get(key)) - _safe_int(creator_action_counts.get(key))
        if value > 0:
            remaining[key] = value
    return remaining


def _summarize_training_history(training_history: dict[str, Any] | None) -> dict[str, Any]:
    payload = training_history or {}
    baseline_heads = dict(payload.get("baseline_heads", {}))
    aggregated = baseline_heads.get("aggregated", [])
    fusion = dict(payload.get("fusion", {}))
    return {
        "available": bool(payload),
        "baseline_heads": {
            "fit_label": baseline_heads.get("fit_label"),
            "eval_label": baseline_heads.get("eval_label"),
            "head_count": len(dict(baseline_heads.get("heads", {}))),
            "aggregated": aggregated if isinstance(aggregated, list) else [],
        },
        "fusion": {
            "fit_label": fusion.get("fit_label"),
            "eval_label": fusion.get("eval_label"),
            "history": fusion.get("history", []) if isinstance(fusion.get("history", []), list) else [],
        },
    }


def _summarize_semantic_routing_eval(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    compact_rows = payload.get("compact_rows", [])
    summary = {key: value for key, value in payload.items() if key != "compact_rows"}
    summary["compact_row_count"] = len(compact_rows) if isinstance(compact_rows, list) else 0
    summary["compact_rows_artifact_only"] = True
    return summary


def build_benchmark_summary() -> dict[str, Any]:
    runtime_governance = persist_runtime_governance_summary()
    paths = _artifact_paths()
    model_info = _read_json_if_exists(paths["model_info"])
    eval_report = _read_json_if_exists(paths["eval_report"])
    simulation = _read_json_if_exists(paths["simulation"])
    training_history = _read_json_if_exists(paths["training_history"])
    semantic_routing_eval = _read_json_if_exists(paths["semantic_routing_eval"])
    semantic_routing_baseline_eval = _read_json_if_exists(paths["semantic_routing_baseline_eval"])
    calibration_decision = _read_json_if_exists(paths["calibration_decision"])
    creative_fpr_diagnostic = _read_json_if_exists(paths["creative_fpr_diagnostic"])
    no_retrain_decision = _read_json_if_exists(paths["no_retrain_decision"])
    no_promotion_decision = _read_json_if_exists(paths["no_promotion_decision"])
    drift_report = _read_json_if_exists(paths["drift_report"])
    runtime_policy = _read_json_if_exists(paths["runtime_policy"])
    thresholds = _read_json_if_exists(paths["thresholds"])
    bseo_policy = _read_json_if_exists(paths["bseo_policy"])
    bseo_report = _read_json_if_exists(paths["bseo_report"])
    mutation_atlas = _read_json_if_exists(paths["mutation_atlas"])
    lineage = read_json(paths["lineage"]) if paths["lineage"] is not None and paths["lineage"].exists() else None
    supplemental_candidates = _read_json_if_exists(paths["supplemental_candidates"])
    supplemental_adjudication = _read_json_if_exists(paths["supplemental_adjudication"])
    supplemental_gold = _read_jsonl_if_exists(paths["supplemental_gold"])
    operator_feedback_manifest = _read_json_if_exists(paths["operator_feedback_manifest"])
    operator_ingestion_manifest = _read_json_if_exists(paths["operator_ingestion_manifest"])
    operator_adjudication = _read_json_if_exists(paths["operator_adjudication"])
    operator_gold = _read_jsonl_if_exists(paths["operator_gold"])
    build_manifest = _read_json_if_exists(paths["build_manifest"])
    browser_observations = summarize_browser_observations()
    feedback_summary = summarize_feedback_events()

    build_id = str(
        (model_info or {}).get("build_id")
        or (eval_report or {}).get("build_id")
        or (simulation or {}).get("build_id")
        or ""
    )
    sample_count = _sample_count(eval_report)
    eval_metrics = dict((eval_report or {}).get("metrics", {}))
    validation_metrics = dict((eval_report or {}).get("validation_metrics", {}))
    model_metrics = dict((model_info or {}).get("metrics", {}))
    per_head_metrics = dict((model_info or {}).get("per_head_metrics", {}))
    threshold_sweep = list((simulation or {}).get("threshold_sweep", []))
    simulation_has_bseo = _is_truthy_bseo_payload(simulation)
    mutation_atlas_payload = _summarize_mutation_atlas(
        dict((simulation or {}).get("bseo_search", {}).get("mutation_bias_atlas", {}))
        if simulation_has_bseo
        else mutation_atlas or {}
    )
    bseo_bias_signature = (
        dict((simulation or {}).get("bseo_search", {}).get("best_bias_signature", {}))
        if simulation_has_bseo
        else dict((bseo_report or {}).get("best_bias_signature", {}))
    )
    bseo_lineage_summary = _summarize_lineage(lineage if isinstance(lineage, list) else None)
    supplemental_intake = _summarize_supplemental_intake(
        supplemental_candidates,
        supplemental_adjudication,
        supplemental_gold,
    )
    operator_feedback = _summarize_operator_feedback(
        operator_feedback_manifest,
        operator_adjudication,
        operator_gold,
        build_manifest,
    )
    global_benchmark_truth = _summarize_global_benchmark_truth(build_manifest, eval_report)
    creator_feedback_summary = dict(feedback_summary.get("creator_operator_feedback", {}))
    creator_total_events = (
        operator_feedback["candidate_count"]
        if operator_feedback["candidate_count"] > 0
        else _safe_int(creator_feedback_summary.get("total_events"))
    )
    creator_action_counts = (
        dict(operator_feedback.get("action_counts", {}))
        if operator_feedback.get("action_counts")
        else dict(creator_feedback_summary.get("action_counts", {}))
    )
    local_user_feedback = {
        "total_events": max(_safe_int(feedback_summary.get("total_events")) - creator_total_events, 0),
        "action_counts": _subtract_action_counts(
            dict(feedback_summary.get("action_counts", {})),
            creator_action_counts,
        ),
    }

    caveats: list[str] = []
    missing: list[str] = []

    if sample_count is None:
        missing.append("eval sample count is unavailable in committed evaluation artifacts")
    elif sample_count < 30:
        caveats.append(
            f"Committed eval sample count is only {sample_count}; metrics are unstable and must not be treated as production benchmarks."
        )
    if eval_metrics and validation_metrics:
        eval_f1 = _safe_float(eval_metrics.get("f1"))
        validation_f1 = _safe_float(validation_metrics.get("f1"))
        if eval_f1 - validation_f1 >= 0.35:
            caveats.append(
                "Validation performance is materially weaker than eval performance; treat the current benchmark as a tiny-sample sanity signal, not a stable generalization claim."
            )
    if not threshold_sweep:
        missing.append("simulation threshold sweep artifact is missing")
    if training_history is None:
        caveats.append(
            "No committed training-history artifact is present, so loss and accuracy curves fall back to explicit unavailable stubs."
        )
    if semantic_routing_eval is None:
        missing.append("semantic-routing-eval artifact is missing")
        caveats.append(
            "No committed route-aware semantic routing evaluation artifact is present, so Adaptive Semantic Evidence Routing cannot be benchmarked from this snapshot."
        )
    if semantic_routing_baseline_eval is None:
        caveats.append(
            "No committed semantic-routing baseline artifact is present, so before/after routing comparison falls back to an unavailable stub."
        )
    if calibration_decision is None:
        missing.append("calibration-decision artifact is missing")
        caveats.append(
            "No committed calibration/hyperparameter decision artifact is present, so tuning or no-tune status is not artifact-backed in this snapshot."
        )
    if creative_fpr_diagnostic is None:
        caveats.append(
            "No creative-FPR diagnostic artifact is present, so the creative false-positive calibration gate is unavailable for this snapshot."
        )
    if runtime_policy is None:
        missing.append("runtime-policy.json is missing")
    if bseo_policy is None:
        caveats.append(
            "No committed configs/thresholds/bseo-policy.json is present at repo root, so BSEO shadow/live remains a code-supported mode rather than a promoted committed runtime artifact."
        )
    if not simulation_has_bseo and not bseo_report:
        caveats.append(
            "Committed simulation artifacts do not currently include populated BSEO search outputs, lineage logs, or mutation atlas data."
        )
    if drift_report is None:
        missing.append("drift report artifact is missing")
    else:
        current_count = _safe_int(drift_report.get("current_count"))
        if current_count < 25:
            caveats.append(
                f"Drift report compares against only {current_count} current rows, so shift readings are directional rather than statistically robust."
            )
    if browser_observations["total_observations"] == 0:
        caveats.append(
            "No browser observation records are currently committed in the repo root, so supplemental intake provenance is structurally supported but not yet benchmark-rich."
        )
    if supplemental_intake["candidate_count"] == 0 and operator_feedback["candidate_count"] == 0:
        caveats.append(
            "No supplemental browser/feedback candidates are currently committed, so intake charts should be read as capability hooks rather than mature operational volume."
        )
    if supplemental_intake.get("collection_scoped_count", 0) == 0:
        caveats.append(
            "No committed collection-scoped review artifacts are present yet, so mix/playlist batch handling is implemented but not benchmark-rich in the repo snapshot."
        )

    policy_mode = str((runtime_policy or {}).get("policy_mode", "threshold-default"))
    resolved_mode = policy_mode
    if policy_mode == "rl-shadow":
        resolved_mode = "bseo-shadow"
    elif policy_mode == "rl-live":
        resolved_mode = "bseo-live"

    runtime_truth = {
        "configured_policy_mode": policy_mode,
        "resolved_policy_mode": resolved_mode,
        "bseo_artifact_committed": bseo_policy is not None,
        "bseo_artifact_compatible": bool(
            isinstance(bseo_policy, dict)
            and str(bseo_policy.get("head_spec_version", "")) == str((model_info or {}).get("head_spec_version", ""))
        ),
        "selective_verification_contract_present": True,
        "heavy_llm_hot_path": False,
        "recommended_policy_mode": str(runtime_governance["promotion"]["recommended_mode"]),
        "max_promotable_mode": str(runtime_governance["promotion"]["max_promotable_mode"]),
        "shadow_eligible": bool(runtime_governance["promotion"]["shadow_eligible"]),
        "live_eligible": bool(runtime_governance["promotion"]["live_eligible"]),
    }

    recommended_mode = str(runtime_governance["promotion"]["recommended_mode"])
    max_promotable_mode = str(runtime_governance["promotion"]["max_promotable_mode"])
    if policy_mode != recommended_mode:
        caveats.append(
            f"Configured runtime mode is `{policy_mode}`, but runtime governance currently recommends `{recommended_mode}` from the committed artifacts and guardrails."
        )
    live_blockers = list(runtime_governance["promotion"]["live_blockers"])
    if live_blockers:
        blocker_text = ", ".join(str(blocker) for blocker in live_blockers)
        caveats.append(
            f"BSEO live is not currently eligible. Max promotable committed mode is `{max_promotable_mode}`. Live blockers: {blocker_text}."
        )

    return {
        "generated_at": _utc_now(),
        "build_id": build_id or None,
        "model_version": (model_info or {}).get("model_version"),
        "trained_at": (model_info or {}).get("trained_at"),
        "sample_count": sample_count,
        "artifact_paths": {name: _relative(path) for name, path in paths.items()},
        "artifact_timestamps": {name: _artifact_timestamp(path) for name, path in paths.items()},
        "runtime_truth": runtime_truth,
        "runtime_governance": runtime_governance,
        "metrics": {
            "eval": eval_metrics,
            "validation": validation_metrics,
            "model_snapshot": model_metrics,
            "calibration_error": _safe_float((eval_report or {}).get("calibration_error")),
            "validation_calibration_error": _safe_float(
                (eval_report or {}).get("validation_calibration_error")
            ),
            "per_head_metrics": per_head_metrics,
            "confusion_matrix": dict((eval_report or {}).get("confusion_matrix", {})),
        },
        "thresholds": thresholds or {},
        "simulation": {
            "threshold_sweep": threshold_sweep,
            "recommended_thresholds": dict((simulation or {}).get("recommended_thresholds", {})),
            "replay_summary": dict((simulation or {}).get("replay_summary", {})),
            "policy": dict((simulation or {}).get("policy", {})),
            "q_table": dict((simulation or {}).get("q_table", {})),
        },
        "training_history": _summarize_training_history(training_history),
        "semantic_routing": _summarize_semantic_routing_eval(semantic_routing_eval),
        "semantic_routing_baseline": _summarize_semantic_routing_eval(semantic_routing_baseline_eval),
        "calibration_decision": calibration_decision or {},
        "creative_fpr_diagnostic": creative_fpr_diagnostic or {},
        "model_decisions": {
            "no_retrain": no_retrain_decision or {},
            "no_promotion": no_promotion_decision or {},
        },
        "drift": drift_report or {},
        "bseo": {
            "policy_artifact": _summarize_bseo_policy_artifact(bseo_policy),
            "report": _summarize_bseo_report(bseo_report),
            "bias_signature": bseo_bias_signature,
            "mutation_bias_atlas": mutation_atlas_payload,
            "lineage": bseo_lineage_summary,
            "available": bool(bseo_policy or bseo_report or simulation_has_bseo),
        },
        "supplemental_intake": {
            "browser_observations": browser_observations,
            "candidate_batch": supplemental_intake,
            "candidate_batch_path": _relative(paths["supplemental_candidates"]),
            "supplemental_adjudication_path": _relative(paths["supplemental_adjudication"]),
            "supplemental_gold_path": _relative(paths["supplemental_gold"]),
        },
        "feedback_layers": {
            "local_user_feedback": local_user_feedback,
            "creator_operator_feedback": {
                **creator_feedback_summary,
                **operator_feedback,
                "total_events": creator_total_events,
                "candidate_events": creator_total_events,
                "manifest_path": _relative(paths["operator_feedback_manifest"]),
                "ingestion_manifest_path": _relative(paths["operator_ingestion_manifest"]),
                "adjudication_path": _relative(paths["operator_adjudication"]),
                "gold_path": _relative(paths["operator_gold"]),
                "ingestion_path": (operator_ingestion_manifest or {}).get("record_path"),
            },
            "global_benchmark_truth": global_benchmark_truth,
        },
        "caveats": caveats,
        "missing_data": missing,
    }


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _wrap_text(value: str, width: int) -> list[str]:
    words = value.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _pretty_label(value: str) -> str:
    return value.replace("_", " ")


def _svg_document(title: str, subtitle: str, width: int, height: int, body: list[str]) -> str:
    escaped_title = escape(title)
    escaped_subtitle = escape(subtitle)
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            "<style>",
            "text { font-family: 'Segoe UI', Arial, sans-serif; fill: #0f172a; }",
            ".title { font-size: 34px; font-weight: 700; }",
            ".subtitle { font-size: 16px; fill: #475569; }",
            ".card { fill: #ffffff; stroke: #cbd5e1; stroke-width: 1.5; rx: 20; }",
            ".accent { fill: #eff6ff; stroke: #60a5fa; stroke-width: 1.5; rx: 20; }",
            ".warn { fill: #fff7ed; stroke: #fb923c; stroke-width: 1.5; rx: 20; }",
            ".label { font-size: 15px; font-weight: 600; fill: #475569; }",
            ".value { font-size: 32px; font-weight: 700; }",
            ".value-compact { font-size: 22px; font-weight: 700; }",
            ".small { font-size: 13px; fill: #64748b; }",
            ".axis { stroke: #94a3b8; stroke-width: 1.2; }",
            ".grid { stroke: #e2e8f0; stroke-width: 1; }",
            ".legend { font-size: 14px; fill: #334155; }",
            ".stub { font-size: 20px; font-weight: 600; }",
            "</style>",
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#f8fafc" />',
            f'<rect x="20" y="20" width="{width - 40}" height="{height - 40}" fill="#ffffff" rx="26" />',
            f'<text class="title" x="52" y="68">{escaped_title}</text>',
            f'<text class="subtitle" x="52" y="98">{escaped_subtitle}</text>',
            *body,
            "</svg>",
        ]
    )


def _card(
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    value: str,
    note: str = "",
    accent: str = "card",
) -> str:
    lines = [f'<rect class="{accent}" x="{x}" y="{y}" width="{width}" height="{height}" rx="20" />']
    lines.append(f'<text class="label" x="{x + 22}" y="{y + 32}">{escape(label)}</text>')
    value_lines = _wrap_text(value, max(16, int((width - 44) / 13)))
    value_class = "value" if len(value_lines) == 1 and len(value_lines[0]) <= 22 else "value-compact"
    for index, line in enumerate(value_lines[:2]):
        lines.append(
            f'<text class="{value_class}" x="{x + 22}" y="{y + 82 + index * 26}">{escape(line)}</text>'
        )
    if note:
        note_start = y + 122 + max(len(value_lines) - 1, 0) * 16
        for index, line in enumerate(_wrap_text(note, max(26, int((width - 44) / 8)))):
            lines.append(f'<text class="small" x="{x + 22}" y="{note_start + index * 18}">{escape(line)}</text>')
    return "\n".join(lines)


def _stub_svg(title: str, subtitle: str, message: str, path: Path) -> None:
    body = [
        '<rect class="warn" x="52" y="132" width="1176" height="230" rx="24" />',
        f'<text class="stub" x="88" y="196">{escape("Data unavailable for this visualization")}</text>',
    ]
    for index, line in enumerate(_wrap_text(message, 104)):
        body.append(f'<text class="subtitle" x="88" y="{244 + index * 22}">{escape(line)}</text>')
    path.write_text(_svg_document(title, subtitle, 1280, 420, body), encoding="utf-8")


def _write_overview_svg(summary: dict[str, Any], path: Path) -> None:
    eval_metrics = dict(summary["metrics"]["eval"])
    validation_metrics = dict(summary["metrics"]["validation"])
    cards = [
        _card(52, 132, 360, 182, "Eval F1", _format_metric(_safe_float(eval_metrics.get("f1"))), "Committed eval snapshot"),
        _card(
            436,
            132,
            360,
            182,
            "Validation F1",
            _format_metric(_safe_float(validation_metrics.get("f1"))),
            "Cross-check against validation split",
        ),
        _card(
            820,
            132,
            360,
            182,
            "Eval sample count",
            str(summary.get("sample_count") or "n/a"),
            "Very small n must be treated as unstable",
            "warn" if (summary.get("sample_count") or 0) < 30 else "accent",
        ),
        _card(52, 338, 360, 182, "Eval precision", _format_metric(_safe_float(eval_metrics.get("precision")))),
        _card(436, 338, 360, 182, "Eval recall", _format_metric(_safe_float(eval_metrics.get("recall")))),
        _card(
            820,
            338,
            360,
            182,
            "Validation calibration",
            _format_metric(_safe_float(summary["metrics"]["validation_calibration_error"])),
            "Calibration remains more informative than the perfect binary snapshot alone.",
        ),
    ]
    path.write_text(
        _svg_document(
            "TruthLens benchmark overview",
            "Current committed evaluation and validation snapshot. Training metrics are not published in the current root artifacts.",
            1240,
            568,
            cards,
        ),
        encoding="utf-8",
    )


def _bar_chart(
    *,
    title: str,
    subtitle: str,
    categories: list[str],
    series: list[tuple[str, str, list[float]]],
    path: Path,
    y_max: float = 1.0,
) -> None:
    if not categories:
        _stub_svg(title, subtitle, "No categories were available in the source artifacts.", path)
        return
    width = 1400
    height = 620
    chart_x = 86
    chart_y = 154
    chart_w = 1240
    chart_h = 340
    group_width = chart_w / max(len(categories), 1)
    bar_width = max(18.0, min(48.0, group_width / max(len(series) + 1, 2)))
    body: list[str] = []
    for step in range(6):
        y = chart_y + chart_h - (chart_h * step / 5.0)
        label = f"{(y_max * step / 5.0):.2f}"
        body.append(f'<line class="grid" x1="{chart_x}" y1="{y:.1f}" x2="{chart_x + chart_w}" y2="{y:.1f}" />')
        body.append(f'<text class="small" x="{chart_x - 48}" y="{y + 5:.1f}">{escape(label)}</text>')
    body.append(f'<line class="axis" x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" />')
    body.append(
        f'<line class="axis" x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" />'
    )
    for category_index, category in enumerate(categories):
        group_x = chart_x + category_index * group_width + 26
        for series_index, (_, color, values) in enumerate(series):
            value = values[category_index]
            safe_value = max(0.0, min(value, y_max))
            bar_height = 0.0 if y_max == 0 else (safe_value / y_max) * chart_h
            x = group_x + series_index * (bar_width + 6)
            y = chart_y + chart_h - bar_height
            body.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}" rx="6" />'
            )
        label_lines = _wrap_text(_pretty_label(category), 16)
        label_x = group_x + group_width / 4
        for line_index, line in enumerate(label_lines[:2]):
            body.append(
                f'<text class="small" x="{label_x:.1f}" y="{chart_y + chart_h + 28 + line_index * 16}" text-anchor="middle">{escape(line)}</text>'
            )
    legend_x = chart_x
    for index, (name, color, _) in enumerate(series):
        item_x = legend_x + index * 220
        body.append(f'<rect x="{item_x}" y="540" width="16" height="16" fill="{color}" rx="4" />')
        body.append(f'<text class="legend" x="{item_x + 24}" y="553">{escape(name)}</text>')
    path.write_text(_svg_document(title, subtitle, width, height, body), encoding="utf-8")


def _write_per_head_svg(summary: dict[str, Any], path: Path) -> None:
    per_head = dict(summary["metrics"]["per_head_metrics"])
    if not per_head:
        _stub_svg(
            "Per-head metrics",
            "Precision / recall / F1 per head",
            "Per-head metrics were not present in model_info.json.",
            path,
        )
        return
    categories = list(per_head.keys())
    precision = [_safe_float(per_head[name].get("metrics", {}).get("precision")) for name in categories]
    recall = [_safe_float(per_head[name].get("metrics", {}).get("recall")) for name in categories]
    f1 = [_safe_float(per_head[name].get("metrics", {}).get("f1")) for name in categories]
    _bar_chart(
        title="Per-head precision / recall / F1",
        subtitle="Derived directly from committed model_info.json. Heads with tiny support can look deceptively strong.",
        categories=categories,
        series=[
            ("Precision", "#2563eb", precision),
            ("Recall", "#0f766e", recall),
            ("F1", "#c2410c", f1),
        ],
        path=path,
    )


def _write_calibration_svg(summary: dict[str, Any], path: Path) -> None:
    per_head = dict(summary["metrics"]["per_head_metrics"])
    categories = list(per_head.keys()) + ["eval", "validation"]
    values = [_safe_float(per_head[name].get("calibration_error")) for name in per_head]
    values.extend(
        [
            _safe_float(summary["metrics"]["calibration_error"]),
            _safe_float(summary["metrics"]["validation_calibration_error"]),
        ]
    )
    _bar_chart(
        title="Calibration error comparison",
        subtitle="Lower is better. Validation calibration can look perfect on tiny samples and should not be over-interpreted.",
        categories=categories,
        series=[("Calibration error", "#7c3aed", values)],
        path=path,
        y_max=max(max(values, default=0.0) * 1.25, 0.35),
    )


def _write_confusion_svg(summary: dict[str, Any], path: Path) -> None:
    confusion = dict(summary["metrics"]["confusion_matrix"])
    if not confusion:
        _stub_svg(
            "Eval confusion matrix",
            "Committed eval confusion counts",
            "Confusion matrix is missing from the evaluation artifact.",
            path,
        )
        return
    values = [
        ("TP", _safe_int(confusion.get("tp"))),
        ("FP", _safe_int(confusion.get("fp"))),
        ("FN", _safe_int(confusion.get("fn"))),
        ("TN", _safe_int(confusion.get("tn"))),
    ]
    max_value = max((value for _, value in values), default=1)
    body: list[str] = []
    positions = {"TP": (120, 140), "FP": (340, 140), "FN": (120, 260), "TN": (340, 260)}
    for label, value in values:
        x, y = positions[label]
        intensity = int(255 - (value / max(max_value, 1)) * 110)
        fill = f"rgb({intensity}, {intensity}, 255)"
        body.append(
            f'<rect x="{x}" y="{y}" width="180" height="90" rx="18" fill="{fill}" stroke="#94a3b8" stroke-width="1.5" />'
        )
        body.append(f'<text class="label" x="{x + 18}" y="{y + 28}">{label}</text>')
        body.append(f'<text class="value" x="{x + 18}" y="{y + 68}">{value}</text>')
    body.append('<text class="small" x="120" y="124">Predicted positive</text>')
    body.append('<text class="small" x="120" y="248">Predicted negative</text>')
    body.append('<text class="small" x="120" y="374">Ground truth split: positive on left, negative on right</text>')
    path.write_text(
        _svg_document(
            "Eval confusion matrix",
            "Counts from the committed eval artifact. With n this small, matrix cells are descriptive, not conclusive.",
            720,
            460,
            body,
        ),
        encoding="utf-8",
    )


def _semantic_eval(summary: dict[str, Any]) -> dict[str, Any]:
    semantic_eval = summary.get("semantic_routing", {})
    return semantic_eval if isinstance(semantic_eval, dict) else {}


def _write_semantic_route_distribution_svg(summary: dict[str, Any], path: Path) -> None:
    semantic_eval = _semantic_eval(summary)
    route_segments = dict(semantic_eval.get("route_segments", {}))
    if not route_segments:
        _stub_svg(
            "Semantic route distribution",
            "Adaptive Semantic Evidence Routing runtime distribution",
            "No semantic-routing-eval artifact was available for this build.",
            path,
        )
        return
    categories = [name for name, payload in route_segments.items() if _safe_int(dict(payload).get("sample_count")) > 0]
    values = [_safe_float(dict(route_segments[name]).get("sample_count")) for name in categories]
    _bar_chart(
        title="Semantic route distribution",
        subtitle="Counts from the mandatory route-aware evaluation sidecar.",
        categories=categories,
        series=[("Rows", "#2563eb", values)],
        path=path,
        y_max=max(max(values, default=0.0), 1.0),
    )


def _write_semantic_route_performance_svg(summary: dict[str, Any], path: Path) -> None:
    semantic_eval = _semantic_eval(summary)
    route_segments = dict(semantic_eval.get("route_segments", {}))
    categories = [name for name, payload in route_segments.items() if _safe_int(dict(payload).get("sample_count")) > 0]
    if not categories:
        _stub_svg(
            "Semantic route performance",
            "Route-segmented F1 and error rates",
            "No route segments were available in the semantic-routing-eval artifact.",
            path,
        )
        return
    f1_values: list[float] = []
    fpr_values: list[float] = []
    fnr_values: list[float] = []
    for name in categories:
        metrics = dict(dict(route_segments[name]).get("metrics", {}))
        f1_values.append(_safe_float(metrics.get("f1")))
        fpr_values.append(_safe_float(metrics.get("false_positive_rate")))
        fnr_values.append(_safe_float(metrics.get("false_negative_rate")))
    _bar_chart(
        title="Semantic route performance",
        subtitle="Route-conditioned benchmark metrics under the current runtime policy chain.",
        categories=categories,
        series=[
            ("F1", "#2563eb", f1_values),
            ("FPR", "#c2410c", fpr_values),
            ("FNR", "#7c3aed", fnr_values),
        ],
        path=path,
    )


def _write_content_class_route_performance_svg(summary: dict[str, Any], path: Path) -> None:
    semantic_eval = _semantic_eval(summary)
    class_segments = dict(semantic_eval.get("content_class_segments", {}))
    categories = [name for name, payload in class_segments.items() if _safe_int(dict(payload).get("sample_count")) > 0]
    if not categories:
        _stub_svg(
            "Content-class route performance",
            "Content-class segmented F1 and false-positive rate",
            "No content-class segments were available in the semantic-routing-eval artifact.",
            path,
        )
        return
    f1_values: list[float] = []
    fpr_values: list[float] = []
    for name in categories:
        metrics = dict(dict(class_segments[name]).get("metrics", {}))
        f1_values.append(_safe_float(metrics.get("f1")))
        fpr_values.append(_safe_float(metrics.get("false_positive_rate")))
    _bar_chart(
        title="Content-class route performance",
        subtitle="Class-segmented metrics. Sparse class support remains a caveat.",
        categories=categories,
        series=[("F1", "#2563eb", f1_values), ("FPR", "#c2410c", fpr_values)],
        path=path,
    )


def _write_recommended_action_distribution_svg(summary: dict[str, Any], path: Path) -> None:
    semantic_eval = _semantic_eval(summary)
    overall = dict(semantic_eval.get("overall", {}))
    distribution = dict(overall.get("recommended_action_distribution", {}))
    if not distribution:
        _stub_svg(
            "Recommended action distribution",
            "Policy action distribution from route-aware evaluation",
            "No recommended-action distribution was available in the semantic-routing-eval artifact.",
            path,
        )
        return
    categories = list(distribution.keys())
    values = [_safe_float(distribution[name]) for name in categories]
    _bar_chart(
        title="Recommended action distribution",
        subtitle="Final user-facing policy actions under the current semantic-routing runtime chain.",
        categories=categories,
        series=[("Actions", "#0f766e", values)],
        path=path,
        y_max=max(max(values, default=0.0), 1.0),
    )


def _write_semantic_route_before_after_svg(summary: dict[str, Any], path: Path) -> None:
    current = _semantic_eval(summary)
    baseline = summary.get("semantic_routing_baseline", {})
    baseline = baseline if isinstance(baseline, dict) else {}
    if not current or not baseline:
        _stub_svg(
            "Semantic route before / after",
            "Old latest model under new routing vs current generated runtime",
            "Both baseline and current semantic-routing eval artifacts are required for this comparison.",
            path,
        )
        return
    categories = ["overall_f1", "creative_fpr", "camouflage_fnr", "bseo_override"]
    current_checks = dict(current.get("architecture_checks", {}))
    baseline_checks = dict(baseline.get("architecture_checks", {}))
    current_values = [
        _safe_float(dict(current.get("overall", {})).get("metrics", {}).get("f1")),
        _safe_float(current_checks.get("creative_false_positive_rate")),
        _safe_float(current_checks.get("deceptive_factual_camouflage_false_negative_rate")),
        _safe_float(current_checks.get("bseo_override_frequency")),
    ]
    baseline_values = [
        _safe_float(dict(baseline.get("overall", {})).get("metrics", {}).get("f1")),
        _safe_float(baseline_checks.get("creative_false_positive_rate")),
        _safe_float(baseline_checks.get("deceptive_factual_camouflage_false_negative_rate")),
        _safe_float(baseline_checks.get("bseo_override_frequency")),
    ]
    _bar_chart(
        title="Semantic route before / after",
        subtitle="Artifact-backed comparison of baseline latest vs current generated runtime under semantic routing.",
        categories=categories,
        series=[
            ("Baseline", "#64748b", baseline_values),
            ("Current", "#2563eb", current_values),
        ],
        path=path,
    )


def _write_creative_fpr_diagnostic_svg(summary: dict[str, Any], path: Path) -> None:
    diagnostic = summary.get("creative_fpr_diagnostic", {})
    diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
    before = dict(diagnostic.get("before", {}))
    after = dict(diagnostic.get("after", {}))
    if not before or not after:
        _stub_svg(
            "Creative FPR diagnostic",
            "Before/after gate for route-aware creative false positives",
            "No creative-FPR diagnostic artifact was available for this build.",
            path,
        )
        return
    categories = ["creative_fpr", "camouflage_fnr", "high_recall", "overall_f1"]
    before_values = [
        _safe_float(before.get("creative_false_positive_rate")),
        _safe_float(before.get("deceptive_factual_camouflage_false_negative_rate")),
        _safe_float(before.get("high_risk_factual_recall")),
        _safe_float(before.get("overall_f1")),
    ]
    after_values = [
        _safe_float(after.get("creative_false_positive_rate")),
        _safe_float(after.get("deceptive_factual_camouflage_false_negative_rate")),
        _safe_float(after.get("high_risk_factual_recall")),
        _safe_float(after.get("overall_f1")),
    ]
    _bar_chart(
        title="Creative FPR diagnostic",
        subtitle="Governed before/after route-aware calibration gate. Lower FPR/FNR is better; higher recall/F1 is better.",
        categories=categories,
        series=[
            ("Before", "#64748b", before_values),
            ("After", "#2563eb", after_values),
        ],
        path=path,
    )


def _write_training_curve_svg(
    summary: dict[str, Any],
    path: Path,
    *,
    metric_name: str,
    title: str,
) -> None:
    training_history = dict(summary.get("training_history", {}))
    baseline = dict(training_history.get("baseline_heads", {}))
    aggregated = baseline.get("aggregated", [])
    if not isinstance(aggregated, list) or not aggregated:
        _stub_svg(
            title,
            "Diagnostic baseline-head history over deterministic iteration checkpoints",
            "No committed training-history artifact was available for this build.",
            path,
        )
        return
    fit_label = str(baseline.get("fit_label") or "train")
    eval_label = str(baseline.get("eval_label") or "validation")
    fit_key = f"{fit_label}_{metric_name}"
    eval_key = f"{eval_label}_{metric_name}"
    iterations = [int(entry.get("iteration", 0)) for entry in aggregated]
    fit_values = [_safe_float(entry.get(fit_key)) for entry in aggregated]
    eval_values = [_safe_float(entry.get(eval_key)) for entry in aggregated]
    if not iterations:
        _stub_svg(
            title,
            "Diagnostic baseline-head history over deterministic iteration checkpoints",
            "The committed training-history artifact did not contain usable checkpoint rows.",
            path,
        )
        return
    width = 1320
    height = 580
    chart_x = 96
    chart_y = 154
    chart_w = 1128
    chart_h = 304
    y_max = max(max(fit_values, default=0.0), max(eval_values, default=0.0), 1.0 if metric_name == "accuracy" else 0.1)
    body: list[str] = []
    for step in range(6):
        y = chart_y + chart_h - (chart_h * step / 5.0)
        label_value = (y_max * step / 5.0)
        body.append(f'<line class="grid" x1="{chart_x}" y1="{y:.1f}" x2="{chart_x + chart_w}" y2="{y:.1f}" />')
        body.append(f'<text class="small" x="{chart_x - 52}" y="{y + 5:.1f}">{label_value:.2f}</text>')
    body.append(f'<line class="axis" x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" />')
    body.append(
        f'<line class="axis" x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" />'
    )

    def _series_points(values: list[float]) -> str:
        points: list[str] = []
        for index, value in enumerate(values):
            x = chart_x + (index / max(len(values) - 1, 1)) * chart_w
            y = chart_y + chart_h - (max(0.0, min(value, y_max)) / max(y_max, 1e-9)) * chart_h
            points.append(f"{x:.1f},{y:.1f}")
        return " ".join(points)

    body.append(f'<polyline fill="none" stroke="#2563eb" stroke-width="3" points="{_series_points(fit_values)}" />')
    body.append(f'<polyline fill="none" stroke="#c2410c" stroke-width="3" points="{_series_points(eval_values)}" />')
    for index, iteration in enumerate(iterations):
        x = chart_x + (index / max(len(iterations) - 1, 1)) * chart_w
        body.append(
            f'<text class="small" x="{x:.1f}" y="{chart_y + chart_h + 30}" text-anchor="middle">{iteration}</text>'
        )
    body.append('<rect x="96" y="516" width="16" height="16" fill="#2563eb" rx="4" />')
    body.append(f'<text class="legend" x="120" y="530">{escape(fit_label.title())} {metric_name}</text>')
    body.append('<rect x="246" y="516" width="16" height="16" fill="#c2410c" rx="4" />')
    body.append(f'<text class="legend" x="270" y="530">{escape(eval_label.title())} {metric_name}</text>')
    body.append(
        '<text class="small" x="96" y="558">Curves average the committed baseline heads over deterministic logistic-regression checkpoints. Fusion diagnostics remain available in the training-history artifact.</text>'
    )
    path.write_text(
        _svg_document(
            title,
            "Derived from the committed training-history artifact. These are diagnostic optimization curves, not new production claims.",
            width,
            height,
            body,
        ),
        encoding="utf-8",
    )


def _write_threshold_sweep_svg(summary: dict[str, Any], path: Path) -> None:
    sweep = list(summary["simulation"]["threshold_sweep"])
    if not sweep:
        _stub_svg(
            "Threshold sweep",
            "Threshold vs F1 and intervention cost",
            "Committed simulation artifacts do not include a threshold sweep with enough data to plot.",
            path,
        )
        return
    width = 1320
    height = 580
    chart_x = 96
    chart_y = 154
    chart_w = 1128
    chart_h = 304
    thresholds = [_safe_float(entry.get("threshold")) for entry in sweep]
    f1_values = [_safe_float(entry.get("f1")) for entry in sweep]
    costs = [_safe_float(entry.get("intervention_cost")) for entry in sweep]
    cost_min = min(costs)
    cost_max = max(costs)
    cost_span = max(cost_max - cost_min, 1e-9)
    normalized_costs = [(value - cost_min) / cost_span for value in costs]
    body: list[str] = []
    for step in range(6):
        y = chart_y + chart_h - (chart_h * step / 5.0)
        body.append(f'<line class="grid" x1="{chart_x}" y1="{y:.1f}" x2="{chart_x + chart_w}" y2="{y:.1f}" />')
        body.append(f'<text class="small" x="{chart_x - 50}" y="{y + 5:.1f}">{step / 5.0:.2f}</text>')
    body.append(f'<line class="axis" x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" />')
    body.append(
        f'<line class="axis" x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" />'
    )

    def _polyline(values: list[float]) -> str:
        points: list[str] = []
        for index, value in enumerate(values):
            x = chart_x + (index / max(len(values) - 1, 1)) * chart_w
            y = chart_y + chart_h - max(0.0, min(value, 1.0)) * chart_h
            points.append(f"{x:.1f},{y:.1f}")
        return " ".join(points)

    body.append(f'<polyline fill="none" stroke="#2563eb" stroke-width="3" points="{_polyline(f1_values)}" />')
    body.append(f'<polyline fill="none" stroke="#c2410c" stroke-width="3" points="{_polyline(normalized_costs)}" />')
    for index, threshold in enumerate(thresholds):
        x = chart_x + (index / max(len(thresholds) - 1, 1)) * chart_w
        body.append(
            f'<text class="small" x="{x:.1f}" y="{chart_y + chart_h + 30}" text-anchor="middle">{threshold:.2f}</text>'
        )
    body.append('<rect x="96" y="516" width="16" height="16" fill="#2563eb" rx="4" />')
    body.append('<text class="legend" x="120" y="530">F1</text>')
    body.append('<rect x="176" y="516" width="16" height="16" fill="#c2410c" rx="4" />')
    body.append('<text class="legend" x="200" y="530">Normalized intervention cost</text>')
    body.append(f'<text class="small" x="96" y="558">Intervention cost range in source artifact: {cost_min:.3f} to {cost_max:.3f}</text>')
    path.write_text(
        _svg_document(
            "Threshold sweep",
            "Blue = F1. Orange = normalized intervention cost. This plot is descriptive only when based on a tiny eval set.",
            width,
            height,
            body,
        ),
        encoding="utf-8",
    )


def _write_drift_svg(summary: dict[str, Any], path: Path) -> None:
    drift = dict(summary["drift"])
    if not drift:
        _stub_svg("Drift summary", "Reference vs current dataset shifts", "No committed drift report is available.", path)
        return
    label_distribution = dict(drift.get("label_distribution_shift", {}))
    shift_pool = [
        ("Channel risk mean", _safe_float(drift.get("channel_risk_mean_shift"))),
        ("Transcript mismatch", _safe_float(drift.get("transcript_mismatch_shift"))),
        ("Thumbnail text density", _safe_float(drift.get("thumbnail_text_density_shift"))),
        ("Title length", _safe_float(drift.get("title_length_shift"))),
        ("Sensational count", _safe_float(drift.get("sensational_count_shift"))),
        ("Template repeat rate", _safe_float(drift.get("repeat_template_rate_shift"))),
        ("Label rate", _safe_float(drift.get("label_rate_shift"))),
    ]
    shift_pool.extend(
        (f"Label mix: {_pretty_label(str(name))}", _safe_float(value))
        for name, value in label_distribution.items()
    )
    metrics = sorted(shift_pool, key=lambda item: abs(item[1]), reverse=True)[:5]
    largest_label, largest_value = metrics[0] if metrics else ("n/a", 0.0)
    triggers = [str(value) for value in drift.get("trigger_reasons", []) if str(value).strip()]
    width = 1240
    height = 640
    chart_x = 240
    chart_y = 320
    chart_w = 930
    chart_h = 220
    max_abs = max(abs(value) for _, value in metrics) or 1.0
    body: list[str] = [
        _card(
            52,
            132,
            274,
            152,
            "Retraining recommended",
            "yes" if bool(drift.get("retraining_recommended")) else "no",
            "This is the drift gate verdict from the committed report.",
            "warn" if bool(drift.get("retraining_recommended")) else "accent",
        ),
        _card(
            350,
            132,
            274,
            152,
            "Trigger reasons",
            ", ".join(triggers) if triggers else "none",
            "No trigger means the current report did not cross a retraining threshold.",
        ),
        _card(
            648,
            132,
            274,
            152,
            "Largest absolute shift",
            f"{largest_label}: {largest_value:+.3f}",
            "Magnitude is shown relative to the reference sample, not as a production guarantee.",
        ),
        _card(
            946,
            132,
            242,
            152,
            "Compared rows",
            f"{_safe_int(drift.get('reference_count'))} -> {_safe_int(drift.get('current_count'))}",
            "Reference rows on the left, current rows on the right.",
        ),
    ]
    zero_x = chart_x + chart_w / 2
    body.append(f'<line class="axis" x1="{zero_x}" y1="{chart_y}" x2="{zero_x}" y2="{chart_y + chart_h}" />')
    for guide in range(5):
        y = chart_y + guide * (chart_h / 4)
        body.append(f'<line class="grid" x1="{chart_x}" y1="{y:.1f}" x2="{chart_x + chart_w}" y2="{y:.1f}" />')
    for index, (label, value) in enumerate(metrics):
        y = chart_y + 18 + index * 40
        span = (abs(value) / max_abs) * (chart_w / 2 - 40)
        if value >= 0:
            x = zero_x
            width_value = span
            color = "#2563eb"
        else:
            x = zero_x - span
            width_value = span
            color = "#c2410c"
        body.append(f'<text class="label" x="52" y="{y + 18}">{escape(label)}</text>')
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width_value:.1f}" height="28" fill="{color}" rx="8" />')
        value_x = zero_x + 10 if value >= 0 else zero_x - 82
        body.append(f'<text class="small" x="{value_x:.1f}" y="{y + 18}">{value:+.3f}</text>')
    body.append(
        '<text class="small" x="52" y="584">Positive means the current sample is higher than the reference sample on that feature. Negative means lower.</text>'
    )
    body.append(
        '<text class="small" x="52" y="606">Near-zero values mean the committed report saw little measured shift on that metric at the current sample size. They do not prove universal no-drift.</text>'
    )
    path.write_text(
        _svg_document(
            "Drift summary",
            "Top signed shifts by magnitude from the committed drift report, with governance interpretation and sample context.",
            width,
            height,
            body,
        ),
        encoding="utf-8",
    )


def _write_policy_svg(summary: dict[str, Any], path: Path) -> None:
    runtime = dict(summary["runtime_truth"])
    body = [
        _card(
            52,
            132,
            360,
            182,
            "Configured runtime mode",
            str(runtime.get("configured_policy_mode", "n/a")),
            "Directly from configs/thresholds/runtime-policy.json",
            "accent",
        ),
        _card(
            436,
            132,
            360,
            182,
            "Resolved runtime mode",
            str(runtime.get("resolved_policy_mode", "n/a")),
            "Aliases normalized for architectural truth",
        ),
        _card(
            820,
            132,
            360,
            182,
            "Committed BSEO artifact",
            "yes" if runtime.get("bseo_artifact_committed") else "no",
            "If absent, shadow/live is code-supported but not promoted as a committed runtime artifact.",
            "warn" if not runtime.get("bseo_artifact_committed") else "accent",
        ),
        _card(
            52,
            338,
            360,
            176,
            "Selective verification",
            "explicit",
            "Selective deep verification exists as a separate contract layer rather than a mandatory hot path.",
        ),
        _card(
            436,
            338,
            360,
            176,
            "Heavy LLM in hot path",
            "no",
            "Gemini/manual-report flows stay downstream of baseline scoring.",
        ),
        _card(
            820,
            338,
            360,
            176,
            "Governance recommendation",
            str(runtime.get("recommended_policy_mode", "n/a")),
            f"Max promotable mode = {runtime.get('max_promotable_mode', 'n/a')}",
            "accent",
        ),
    ]
    path.write_text(
        _svg_document(
            "Policy mode and runtime eligibility",
            "This panel is derived from committed runtime config and artifact presence, not from aspirational docs.",
            1240,
            562,
            body,
        ),
        encoding="utf-8",
    )


def _write_runtime_governance_svg(summary: dict[str, Any], path: Path) -> None:
    governance = dict(summary["runtime_governance"])
    promotion = dict(governance.get("promotion", {}))
    performance = dict(governance.get("performance", {}))
    artifacts = dict(governance.get("artifacts", {}))
    dataset = dict(governance.get("dataset", {}))
    live_blockers = list(promotion.get("live_blockers", []))
    live_blocker_text = ", ".join(str(value) for value in live_blockers[:4]) or "none"
    body = [
        _card(
            52,
            132,
            360,
            188,
            "Recommended mode",
            str(promotion.get("recommended_mode", "n/a")),
            "The highest runtime mode currently justified by committed artifacts and guardrails.",
            "accent" if str(promotion.get("recommended_mode", "")) != "threshold-default" else "warn",
        ),
        _card(
            436,
            132,
            360,
            188,
            "Max promotable mode",
            str(promotion.get("max_promotable_mode", "n/a")),
            "Live is only eligible after calibration, lineage, atlas, and shadow-soak checks pass.",
        ),
        _card(
            820,
            132,
            360,
            188,
            "Current eval footprint",
            f"test={_safe_int(dataset.get('test_count'))} | eval={_safe_int(dataset.get('eval_sample_count'))}",
            "Governance summaries are only credible when dataset counts are large enough to matter.",
        ),
        _card(
            52,
            346,
            360,
            188,
            "Objective + calibration",
            f"obj={_safe_float(performance.get('bseo_objective_score')):.3f} | ece={_safe_float(performance.get('calibration_error')):.3f}",
            "BSEO promotion stays downstream of fused/calibrated scoring quality.",
        ),
        _card(
            436,
            346,
            360,
            188,
            "Atlas + lineage",
            f"{artifacts.get('mutation_atlas_status', 'n/a')} | lineage={_safe_int(artifacts.get('lineage_count'))}",
            f"usable_mutations={_safe_int(artifacts.get('usable_mutations'))}",
        ),
        _card(
            820,
            346,
            360,
            188,
            "Live blockers",
            live_blocker_text,
            f"shadow_observations={_safe_int(performance.get('shadow_observation_count'))}",
            "warn" if live_blockers else "accent",
        ),
    ]
    path.write_text(
        _svg_document(
            "Runtime governance summary",
            "Promotion truth from committed BSEO artifacts, performance guardrails, and observed shadow history.",
            1240,
            582,
            body,
        ),
        encoding="utf-8",
    )


def _write_observation_feedback_intake_svg(summary: dict[str, Any], path: Path) -> None:
    intake = dict(summary["supplemental_intake"])
    observation_summary = dict(intake.get("browser_observations", {}))
    candidate_summary = dict(intake.get("candidate_batch", {}))
    feedback_layers = dict(summary.get("feedback_layers", {}))
    local_user_feedback = dict(feedback_layers.get("local_user_feedback", {}))
    creator_feedback = dict(feedback_layers.get("creator_operator_feedback", {}))
    global_truth = dict(feedback_layers.get("global_benchmark_truth", {}))
    body = [
        _card(
            52,
            132,
            360,
            188,
            "Browser observations",
            str(_safe_int(observation_summary.get("total_observations"))),
            f"unique_items={_safe_int(observation_summary.get('unique_items'))}, score_links={_safe_int(observation_summary.get('with_score_link'))}",
        ),
        _card(
            436,
            132,
            360,
            188,
            "Local user feedback",
            str(_safe_int(local_user_feedback.get("total_events"))),
            "Ordinary local-user feedback stays in the runtime/local optimization layer unless it is explicitly curated elsewhere.",
        ),
        _card(
            820,
            132,
            360,
            188,
            "Creator/operator candidates",
            str(_safe_int(creator_feedback.get("candidate_count"))),
            f"gold={_safe_int(creator_feedback.get('gold_count'))}, ingested={_safe_int(creator_feedback.get('ingested_count'))}",
        ),
        _card(
            52,
            346,
            360,
            188,
            "Legacy supplemental intake",
            str(_safe_int(candidate_summary.get("candidate_count"))),
            f"split_blocked={_safe_int(candidate_summary.get('split_blocked_count'))}, adjudicated={_safe_int(candidate_summary.get('adjudicated_count'))}",
        ),
        _card(
            436,
            346,
            360,
            188,
            "Creator/operator adjudication",
            str(_safe_int(creator_feedback.get("adjudicated_count"))),
            f"confirmed_risk={_safe_int(creator_feedback.get('confirmed_risk_count'))}, confirmed_benign={_safe_int(creator_feedback.get('confirmed_benign_count'))}",
        ),
        _card(
            820,
            346,
            360,
            188,
            "Global benchmark truth",
            f"{_safe_int(global_truth.get('total_records'))}",
            f"train={_safe_int(global_truth.get('train_count'))}, validation={_safe_int(global_truth.get('validation_count'))}, test={_safe_int(global_truth.get('test_count'))}",
            "accent",
        ),
    ]
    path.write_text(
        _svg_document(
            "Observation and feedback intake",
            "Local feedback, creator/operator curation, and global benchmark truth are rendered as separate operational layers.",
            1240,
            582,
            body,
        ),
        encoding="utf-8",
    )


def _write_provenance_svg(summary: dict[str, Any], path: Path) -> None:
    build_id = str(summary.get("build_id") or "n/a")
    model_version = str(summary.get("model_version") or "n/a")
    trained_at = str(summary.get("trained_at") or "n/a")
    sample_count = str(summary.get("sample_count") or "n/a")
    timestamps = summary.get("artifact_timestamps", {})
    cards = [
        _card(52, 132, 360, 182, "Build ID", build_id, "Artifact lineage anchor"),
        _card(436, 132, 360, 182, "Model version", model_version, "Snapshot from trained model info"),
        _card(820, 132, 360, 182, "Eval sample count", sample_count, "Committed evaluation sample size"),
        _card(
            52,
            338,
            1128,
            176,
            "Artifact timestamps",
            "committed",
            f"model_info={timestamps.get('model_info')} | eval={timestamps.get('eval_report')} | drift={timestamps.get('drift_report')}",
        ),
        _card(
            52,
            536,
            1128,
            170,
            "Training timestamp",
            trained_at,
            "If this timestamp and current docs diverge, the docs are stale.",
        ),
    ]
    path.write_text(
        _svg_document(
            "Benchmark provenance",
            "Every benchmark claim in README should trace back to these committed artifacts.",
            1240,
            756,
            cards,
        ),
        encoding="utf-8",
    )


def _write_bseo_bias_svg(summary: dict[str, Any], path: Path) -> None:
    bias_signature = dict(summary["bseo"]["bias_signature"])
    macro = dict(bias_signature.get("macro", {}))
    if not macro:
        _stub_svg(
            "BSEO bias profile",
            "Macro bias signature from committed BSEO artifacts",
            "No committed BSEO bias signature was available. This is expected when the root repo has not promoted a bseo-policy artifact or populated bseo simulation output.",
            path,
        )
        return
    categories = list(macro.keys())
    values = [_safe_float(macro[name]) for name in categories]
    _bar_chart(
        title="BSEO macro bias profile",
        subtitle="Lower is generally better for negative-bias accumulation. Read in conjunction with sample-size caveats.",
        categories=categories,
        series=[("Macro bias", "#7c3aed", values)],
        path=path,
        y_max=max(max(values, default=0.0) * 1.3, 0.45),
    )


def _write_mutation_atlas_svg(summary: dict[str, Any], path: Path) -> None:
    atlas = dict(summary["bseo"]["mutation_bias_atlas"])
    status = str(atlas.get("status", "missing"))
    if not atlas:
        _stub_svg(
            "Mutation bias atlas",
            "Cluster summary from BSEO lineage logs",
            "No committed mutation atlas artifact was available.",
            path,
        )
        return
    clusters = atlas.get("clusters", [])
    if status == "sparse":
        _stub_svg(
            "Mutation bias atlas",
            "Cluster summary from BSEO lineage logs",
            f"Atlas is marked sparse with only {_safe_int(atlas.get('usable_mutations'))} usable accepted mutations.",
            path,
        )
        return
    body = [
        _card(52, 132, 360, 182, "Atlas status", status),
        _card(436, 132, 360, 182, "Usable mutations", str(_safe_int(atlas.get("usable_mutations")))),
        _card(820, 132, 360, 182, "Cluster count", str(len(clusters))),
    ]
    for index, cluster in enumerate(clusters[:3]):
        body.append(
            _card(
                52 + index * 384,
                338,
                360,
                182,
                f"Cluster {cluster.get('cluster_id')}",
                f"size={_safe_int(cluster.get('size'))}",
                f"avg dF={_safe_float(cluster.get('average_delta_f')):.3f}, avg dB={_safe_float(cluster.get('average_delta_b')):.3f}",
            )
        )
    path.write_text(
        _svg_document(
            "Mutation bias atlas",
            "Cluster overview from committed BSEO lineage artifacts.",
            1240,
            568,
            body,
        ),
        encoding="utf-8",
    )


def _write_lineage_svg(summary: dict[str, Any], path: Path) -> None:
    lineage = dict(summary["bseo"]["lineage"])
    accepted = list(lineage.get("accepted_preview", []))
    if not accepted:
        _stub_svg(
            "Lineage overview",
            "Accepted mutation trajectory",
            "No committed lineage log was available to render.",
            path,
        )
        return
    categories = [str(entry.get("candidate_id")) for entry in accepted[:8]]
    objective = [_safe_float(entry.get("objective")) for entry in accepted[:8]]
    _bar_chart(
        title="Accepted lineage objective scores",
        subtitle="Accepted lineage preview from the committed summary. Raw lineage remains in the eval artifact path.",
        categories=categories,
        series=[("Objective", "#2563eb", objective)],
        path=path,
        y_max=max(max(objective, default=0.0) * 1.15, 0.9),
    )


def _overall_metrics_table(summary: dict[str, Any]) -> str:
    eval_metrics = dict(summary["metrics"]["eval"])
    validation_metrics = dict(summary["metrics"]["validation"])
    rows = [
        ("Precision", _safe_float(eval_metrics.get("precision")), _safe_float(validation_metrics.get("precision"))),
        ("Recall", _safe_float(eval_metrics.get("recall")), _safe_float(validation_metrics.get("recall"))),
        ("F1", _safe_float(eval_metrics.get("f1")), _safe_float(validation_metrics.get("f1"))),
        ("ROC AUC", _safe_float(eval_metrics.get("roc_auc")), _safe_float(validation_metrics.get("roc_auc"))),
        ("PR AUC", _safe_float(eval_metrics.get("pr_auc")), _safe_float(validation_metrics.get("pr_auc"))),
        (
            "Calibration error",
            _safe_float(summary["metrics"]["calibration_error"]),
            _safe_float(summary["metrics"]["validation_calibration_error"]),
        ),
    ]
    lines = [
        "| Metric | Eval | Validation |",
        "| --- | ---: | ---: |",
    ]
    for name, eval_value, validation_value in rows:
        lines.append(f"| {name} | {_format_metric(eval_value)} | {_format_metric(validation_value)} |")
    return "\n".join(lines) + "\n"


def _benchmark_summary_markdown(summary: dict[str, Any]) -> str:
    governance = dict(summary["runtime_governance"])
    promotion = dict(governance.get("promotion", {}))
    intake = dict(summary["supplemental_intake"])
    browser_observations = dict(intake.get("browser_observations", {}))
    candidate_batch = dict(intake.get("candidate_batch", {}))
    feedback_layers = dict(summary.get("feedback_layers", {}))
    local_user_feedback = dict(feedback_layers.get("local_user_feedback", {}))
    creator_feedback = dict(feedback_layers.get("creator_operator_feedback", {}))
    global_truth = dict(feedback_layers.get("global_benchmark_truth", {}))
    semantic_eval = _semantic_eval(summary)
    architecture_checks = dict(semantic_eval.get("architecture_checks", {}))
    calibration_decision = dict(summary.get("calibration_decision", {}))
    creative_diagnostic = dict(summary.get("creative_fpr_diagnostic", {}))
    creative_before = dict(creative_diagnostic.get("before", {}))
    creative_after = dict(creative_diagnostic.get("after", {}))
    lines = [
        "# Benchmark Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Build ID: `{summary.get('build_id') or 'n/a'}`",
        f"- Model version: `{summary.get('model_version') or 'n/a'}`",
        f"- Eval sample count: `{summary.get('sample_count') or 'n/a'}`",
        f"- Configured runtime policy mode: `{summary['runtime_truth']['configured_policy_mode']}`",
        f"- Resolved runtime policy mode: `{summary['runtime_truth']['resolved_policy_mode']}`",
        f"- Governance recommended mode: `{promotion.get('recommended_mode', 'n/a')}`",
        f"- Max promotable mode: `{promotion.get('max_promotable_mode', 'n/a')}`",
        "",
        "## Metrics",
        "",
        _overall_metrics_table(summary).rstrip(),
        "",
        "## Adaptive Semantic Evidence Routing Eval",
        "",
        f"- Route-aware eval artifact: `{summary['artifact_paths'].get('semantic_routing_eval') or 'missing'}`",
        f"- Route-aware baseline artifact: `{summary['artifact_paths'].get('semantic_routing_baseline_eval') or 'missing'}`",
        f"- Calibration decision artifact: `{summary['artifact_paths'].get('calibration_decision') or 'missing'}`",
        f"- Creative FPR diagnostic artifact: `{summary['artifact_paths'].get('creative_fpr_diagnostic') or 'missing'}`",
        f"- Route-aware sample count: `{semantic_eval.get('sample_count', 0)}`",
        f"- Creative false-positive rate: `{architecture_checks.get('creative_false_positive_rate', 'n/a')}`",
        f"- Deceptive/factual camouflage false-negative rate: `{architecture_checks.get('deceptive_factual_camouflage_false_negative_rate', 'n/a')}`",
        f"- BSEO override frequency: `{architecture_checks.get('bseo_override_frequency', 'n/a')}`",
        f"- Calibration decision: `{calibration_decision.get('decision', 'missing')}`",
        f"- Creative FPR gate accepted: `{creative_diagnostic.get('accepted', 'missing')}`",
        f"- Creative FPR before/after: `{creative_before.get('creative_false_positive_rate', 'n/a')}` -> `{creative_after.get('creative_false_positive_rate', 'n/a')}`",
        "",
        "## Observation And Feedback Intake",
        "",
        f"- Browser observations: `{browser_observations.get('total_observations', 0)}`",
        f"- Unique observed items: `{browser_observations.get('unique_items', 0)}`",
        f"- Observation rows linked back to scored items: `{browser_observations.get('with_score_link', 0)}`",
        f"- Legacy supplemental candidates: `{candidate_batch.get('candidate_count', 0)}`",
        f"- Legacy split-blocked candidates: `{candidate_batch.get('split_blocked_count', 0)}`",
        f"- Local-user feedback events: `{local_user_feedback.get('total_events', 0)}`",
        f"- Creator/operator candidates: `{creator_feedback.get('candidate_count', 0)}`",
        f"- Creator/operator gold rows: `{creator_feedback.get('gold_count', 0)}`",
        f"- Creator/operator ingested rows: `{creator_feedback.get('ingested_count', 0)}`",
        f"- Global benchmark truth rows: `{global_truth.get('total_records', 0)}`",
        "",
        "## Runtime Governance",
        "",
        f"- Shadow eligible: `{promotion.get('shadow_eligible', False)}`",
        f"- Live eligible: `{promotion.get('live_eligible', False)}`",
        f"- Shadow observation count: `{governance.get('performance', {}).get('shadow_observation_count', 0)}`",
        f"- BSEO objective score: `{governance.get('performance', {}).get('bseo_objective_score', 'n/a')}`",
    ]
    shadow_blockers = list(promotion.get("shadow_blockers", []))
    live_blockers = list(promotion.get("live_blockers", []))
    if shadow_blockers:
        lines.append(f"- Shadow blockers: `{', '.join(str(value) for value in shadow_blockers)}`")
    if live_blockers:
        lines.append(f"- Live blockers: `{', '.join(str(value) for value in live_blockers)}`")
    lines.extend(["", "## Caveats", ""])
    if summary["caveats"]:
        for caveat in summary["caveats"]:
            lines.append(f"- {caveat}")
    else:
        lines.append("- No benchmark caveats were inferred from the committed artifacts.")
    lines.extend(["", "## Missing Data", ""])
    if summary["missing_data"]:
        for item in summary["missing_data"]:
            lines.append(f"- {item}")
    else:
        lines.append("- No missing benchmark inputs were detected.")
    lines.extend(["", "## Artifact Provenance", ""])
    for name, path_value in summary["artifact_paths"].items():
        lines.append(f"- `{name}`: `{path_value or 'missing'}`")
    return "\n".join(lines) + "\n"


def _write_dashboard(summary: dict[str, Any], path: Path, title: str, body_html: str) -> None:
    payload = json.dumps(
        {
            "build_id": summary.get("build_id"),
            "model_version": summary.get("model_version"),
            "sample_count": summary.get("sample_count"),
            "runtime_truth": summary.get("runtime_truth"),
            "runtime_governance": summary.get("runtime_governance"),
            "metrics": summary.get("metrics"),
            "caveats": summary.get("caveats"),
            "artifact_paths": summary.get("artifact_paths"),
        },
        indent=2,
        ensure_ascii=True,
    )
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{escape(title)}</title>
    <style>
      body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 0; color: #0f172a; background: #f8fafc; }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
      h1, h2 {{ margin-top: 0; }}
      .card {{ background: white; border: 1px solid #cbd5e1; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.05); }}
      .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 18px; }}
      .metric {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 16px; padding: 16px; }}
      .metric.warn {{ background: #fff7ed; border-color: #fdba74; }}
      .metric strong {{ display: block; font-size: 13px; color: #475569; margin-bottom: 8px; }}
      .metric span {{ display: block; font-size: 28px; font-weight: 700; }}
      code, pre {{ background: #0f172a; color: #e2e8f0; border-radius: 12px; padding: 12px; overflow: auto; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #cbd5e1; padding: 10px 12px; text-align: left; }}
      th {{ background: #eff6ff; }}
      .warn {{ background: #fff7ed; border-color: #fdba74; }}
      .muted {{ color: #475569; }}
      ul {{ margin: 0; padding-left: 20px; }}
    </style>
  </head>
  <body>
    <main>
      <div class="card">
        <h1>{escape(title)}</h1>
        <p class="muted">Generated from committed artifacts. This page is static, deterministic, and should agree with README and the benchmark summary JSON.</p>
      </div>
      {body_html}
      <div class="card">
        <h2>Embedded summary payload</h2>
        <pre>{escape(payload)}</pre>
      </div>
    </main>
  </body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _write_interactive_dashboards(summary: dict[str, Any], output_dir: Path) -> None:
    governance = dict(summary["runtime_governance"])
    promotion = dict(governance.get("promotion", {}))
    metrics_rows = "\n".join(
        f"<tr><td>{escape(name)}</td><td>{escape(_format_metric(_safe_float(summary['metrics']['eval'].get(key))))}</td><td>{escape(_format_metric(_safe_float(summary['metrics']['validation'].get(key))))}</td></tr>"
        for name, key in [
            ("Precision", "precision"),
            ("Recall", "recall"),
            ("F1", "f1"),
            ("ROC AUC", "roc_auc"),
            ("PR AUC", "pr_auc"),
        ]
    )
    caveats = "".join(f"<li>{escape(text)}</li>" for text in summary["caveats"]) or "<li>No caveats inferred.</li>"
    _write_dashboard(
        summary,
        output_dir / "metrics_dashboard.html",
        "TruthLens metrics dashboard",
        f"""
        <div class="card">
          <h2>Current snapshot</h2>
          <div class="metric-grid">
            <div class="metric"><strong>Build ID</strong><span>{escape(str(summary.get('build_id') or 'n/a'))}</span></div>
            <div class="metric"><strong>Eval sample count</strong><span>{escape(str(summary.get('sample_count') or 'n/a'))}</span></div>
            <div class="metric"><strong>Configured mode</strong><span>{escape(str(summary['runtime_truth']['configured_policy_mode']))}</span></div>
            <div class="metric"><strong>Recommended mode</strong><span>{escape(str(summary['runtime_truth']['recommended_policy_mode']))}</span></div>
          </div>
        </div>
        <div class="card">
          <h2>Eval vs validation</h2>
          <table>
            <thead><tr><th>Metric</th><th>Eval</th><th>Validation</th></tr></thead>
            <tbody>{metrics_rows}</tbody>
          </table>
        </div>
        <div class="card warn">
          <h2>Caveats</h2>
          <ul>{caveats}</ul>
        </div>
        """,
    )

    sweep_rows = "".join(
        f"<tr><td>{_safe_float(entry.get('threshold')):.2f}</td><td>{_safe_float(entry.get('f1')):.3f}</td><td>{_safe_float(entry.get('intervention_cost')):.3f}</td></tr>"
        for entry in summary["simulation"]["threshold_sweep"]
    )
    if not sweep_rows:
        sweep_rows = "<tr><td colspan='3'>No threshold sweep available.</td></tr>"
    _write_dashboard(
        summary,
        output_dir / "threshold_explorer.html",
        "TruthLens threshold explorer",
        f"""
        <div class="card">
          <div class="metric-grid">
            <div class="metric"><strong>Build ID</strong><span>{escape(str(summary.get('build_id') or 'n/a'))}</span></div>
            <div class="metric"><strong>Sweep points</strong><span>{escape(str(len(summary["simulation"]["threshold_sweep"])))}</span></div>
          </div>
        </div>
        <div class="card">
          <h2>Threshold sweep table</h2>
          <table>
            <thead><tr><th>Threshold</th><th>F1</th><th>Intervention cost</th></tr></thead>
            <tbody>{sweep_rows}</tbody>
          </table>
        </div>
        """,
    )

    bseo_bias = dict(summary["bseo"]["bias_signature"]).get("macro", {})
    bseo_rows = "".join(
        f"<tr><td>{escape(str(name))}</td><td>{_safe_float(value):.3f}</td></tr>"
        for name, value in bseo_bias.items()
    )
    if not bseo_rows:
        bseo_rows = "<tr><td colspan='2'>No committed BSEO bias profile is available.</td></tr>"
    _write_dashboard(
        summary,
        output_dir / "bseo_policy_dashboard.html",
        "TruthLens BSEO policy dashboard",
        f"""
        <div class="card">
          <h2>Runtime policy truth</h2>
          <div class="metric-grid">
            <div class="metric"><strong>Configured mode</strong><span>{escape(str(summary['runtime_truth']['configured_policy_mode']))}</span></div>
            <div class="metric"><strong>Resolved mode</strong><span>{escape(str(summary['runtime_truth']['resolved_policy_mode']))}</span></div>
            <div class="metric"><strong>Recommended mode</strong><span>{escape(str(summary['runtime_truth']['recommended_policy_mode']))}</span></div>
            <div class="metric"><strong>Max promotable mode</strong><span>{escape(str(summary['runtime_truth']['max_promotable_mode']))}</span></div>
            <div class="metric"><strong>Committed BSEO artifact</strong><span>{escape('yes' if summary['runtime_truth']['bseo_artifact_committed'] else 'no')}</span></div>
          </div>
        </div>
        <div class="card">
          <h2>BSEO macro bias profile</h2>
          <table>
            <thead><tr><th>Bias primitive</th><th>Macro value</th></tr></thead>
            <tbody>{bseo_rows}</tbody>
          </table>
        </div>
        """,
    )

    atlas = dict(summary["bseo"]["mutation_bias_atlas"])
    cluster_rows = "".join(
        f"<tr><td>{_safe_int(cluster.get('cluster_id'))}</td><td>{_safe_int(cluster.get('size'))}</td><td>{_safe_float(cluster.get('average_delta_f')):.3f}</td><td>{_safe_float(cluster.get('average_delta_b')):.3f}</td></tr>"
        for cluster in atlas.get("clusters", [])
    )
    if not cluster_rows:
        cluster_rows = "<tr><td colspan='4'>No committed mutation atlas clusters are available.</td></tr>"
    _write_dashboard(
        summary,
        output_dir / "mutation_atlas.html",
        "TruthLens mutation atlas explorer",
        f"""
        <div class="card">
          <h2>Atlas status</h2>
          <div class="metric-grid">
            <div class="metric"><strong>Status</strong><span>{escape(str(atlas.get('status', 'missing')))}</span></div>
            <div class="metric"><strong>Usable mutations</strong><span>{escape(str(_safe_int(atlas.get('usable_mutations'))))}</span></div>
            <div class="metric"><strong>Cluster count</strong><span>{escape(str(len(atlas.get('clusters', []))))}</span></div>
          </div>
        </div>
        <div class="card">
          <h2>Clusters</h2>
          <table>
            <thead><tr><th>Cluster</th><th>Size</th><th>Average delta F</th><th>Average delta B</th></tr></thead>
            <tbody>{cluster_rows}</tbody>
          </table>
        </div>
        """,
    )

    shadow_blockers = "".join(
        f"<li>{escape(str(value))}</li>" for value in promotion.get("shadow_blockers", [])
    ) or "<li>No shadow blockers.</li>"
    live_blockers = "".join(
        f"<li>{escape(str(value))}</li>" for value in promotion.get("live_blockers", [])
    ) or "<li>No live blockers.</li>"
    _write_dashboard(
        summary,
        output_dir / "runtime_governance_dashboard.html",
        "TruthLens runtime governance dashboard",
        f"""
        <div class="card">
          <h2>Promotion truth</h2>
          <div class="metric-grid">
            <div class="metric"><strong>Configured mode</strong><span>{escape(str(summary['runtime_truth']['configured_policy_mode']))}</span></div>
            <div class="metric"><strong>Recommended mode</strong><span>{escape(str(promotion.get('recommended_mode', 'n/a')))}</span></div>
            <div class="metric"><strong>Max promotable mode</strong><span>{escape(str(promotion.get('max_promotable_mode', 'n/a')))}</span></div>
            <div class="metric"><strong>Shadow eligible</strong><span>{escape(str(promotion.get('shadow_eligible', False)))}</span></div>
            <div class="metric"><strong>Live eligible</strong><span>{escape(str(promotion.get('live_eligible', False)))}</span></div>
          </div>
        </div>
        <div class="card">
          <h2>Observed runtime evidence</h2>
          <div class="metric-grid">
            <div class="metric"><strong>Shadow observations</strong><span>{escape(str(_safe_int(dict(governance.get('performance', {})).get('shadow_observation_count'))))}</span></div>
            <div class="metric"><strong>Eval sample count</strong><span>{escape(str(_safe_int(dict(governance.get('dataset', {})).get('eval_sample_count'))))}</span></div>
            <div class="metric"><strong>Mutation atlas status</strong><span>{escape(str(dict(governance.get('artifacts', {})).get('mutation_atlas_status', 'n/a')))}</span></div>
          </div>
        </div>
        <div class="card warn">
          <h2>Shadow blockers</h2>
          <ul>{shadow_blockers}</ul>
        </div>
        <div class="card warn">
          <h2>Live blockers</h2>
          <ul>{live_blockers}</ul>
        </div>
        """,
    )

    semantic_eval = _semantic_eval(summary)
    route_segments = dict(semantic_eval.get("route_segments", {}))
    route_rows = "".join(
        "<tr>"
        f"<td>{escape(str(route_name))}</td>"
        f"<td>{_safe_int(dict(payload).get('sample_count'))}</td>"
        f"<td>{_safe_float(dict(dict(payload).get('metrics', {})).get('f1')):.3f}</td>"
        f"<td>{_safe_float(dict(dict(payload).get('metrics', {})).get('false_positive_rate')):.3f}</td>"
        f"<td>{_safe_float(dict(dict(payload).get('metrics', {})).get('false_negative_rate')):.3f}</td>"
        "</tr>"
        for route_name, payload in route_segments.items()
        if _safe_int(dict(payload).get("sample_count")) > 0
    )
    if not route_rows:
        route_rows = "<tr><td colspan='5'>No semantic routing evaluation artifact is available.</td></tr>"
    architecture_checks = dict(semantic_eval.get("architecture_checks", {}))
    score_contract = dict(architecture_checks.get("score_contract", {}))
    calibration_decision = dict(summary.get("calibration_decision", {}))
    creative_diagnostic = dict(summary.get("creative_fpr_diagnostic", {}))
    _write_dashboard(
        summary,
        output_dir / "semantic_routing_dashboard.html",
        "TruthLens semantic routing dashboard",
        f"""
        <div class="card">
          <h2>Route-aware evaluation</h2>
          <div class="metric-grid">
            <div class="metric"><strong>Eval artifact</strong><span>{escape(str(summary['artifact_paths'].get('semantic_routing_eval') or 'missing'))}</span></div>
            <div class="metric"><strong>Baseline artifact</strong><span>{escape(str(summary['artifact_paths'].get('semantic_routing_baseline_eval') or 'missing'))}</span></div>
            <div class="metric"><strong>Rows</strong><span>{escape(str(_safe_int(semantic_eval.get('sample_count'))))}</span></div>
            <div class="metric"><strong>Creative FPR</strong><span>{escape(_format_metric(_safe_float(architecture_checks.get('creative_false_positive_rate'))))}</span></div>
            <div class="metric"><strong>Camouflage FNR</strong><span>{escape(_format_metric(_safe_float(architecture_checks.get('deceptive_factual_camouflage_false_negative_rate'))))}</span></div>
            <div class="metric"><strong>BSEO override frequency</strong><span>{escape(_format_metric(_safe_float(architecture_checks.get('bseo_override_frequency'))))}</span></div>
            <div class="metric"><strong>Score contract bounded</strong><span>{escape(str(score_contract.get('bounded_outputs', False)))}</span></div>
          </div>
        </div>
        <div class="card">
          <h2>Routes</h2>
          <table>
            <thead><tr><th>Route</th><th>Rows</th><th>F1</th><th>FPR</th><th>FNR</th></tr></thead>
            <tbody>{route_rows}</tbody>
          </table>
        </div>
        <div class="card">
          <h2>Calibration decision</h2>
          <p>Decision: <code>{escape(str(calibration_decision.get('decision', 'missing')))}</code></p>
          <p>Reason: {escape(str(calibration_decision.get('reason', 'No calibration decision artifact was available.')))}</p>
        </div>
        <div class="card">
          <h2>Creative FPR diagnostic</h2>
          <p>Accepted: <code>{escape(str(creative_diagnostic.get('accepted', 'missing')))}</code></p>
          <p>Artifact: <code>{escape(str(summary['artifact_paths'].get('creative_fpr_diagnostic') or 'missing'))}</code></p>
        </div>
        """,
    )


def render_benchmark_bundle(output_root: Path | None = None) -> dict[str, Any]:
    root = output_root or (repo_root() / "docs" / "benchmarks" / "latest")
    assets_dir = ensure_dir(root / "assets")
    interactive_dir = ensure_dir(root / "interactive")

    summary = build_benchmark_summary()
    public_artifact_replacements = _publish_curated_artifact_paths(_artifact_paths(), root)
    summary = _remap_public_artifact_references(summary, public_artifact_replacements)
    write_json(root / "benchmark_summary.json", summary)
    (root / "benchmark_summary.md").write_text(_benchmark_summary_markdown(summary), encoding="utf-8")
    (assets_dir / "overall_metrics_table.md").write_text(_overall_metrics_table(summary), encoding="utf-8")

    _write_overview_svg(summary, assets_dir / "train_validation_eval_overview.svg")
    _write_per_head_svg(summary, assets_dir / "per_head_metrics.svg")
    _write_calibration_svg(summary, assets_dir / "calibration_error.svg")
    _write_confusion_svg(summary, assets_dir / "confusion_matrix_eval.svg")
    _write_training_curve_svg(
        summary,
        assets_dir / "training_loss_curve.svg",
        metric_name="loss",
        title="Training loss curve",
    )
    _write_training_curve_svg(
        summary,
        assets_dir / "training_accuracy_curve.svg",
        metric_name="accuracy",
        title="Training accuracy curve",
    )
    _write_threshold_sweep_svg(summary, assets_dir / "threshold_sweep.svg")
    _write_drift_svg(summary, assets_dir / "drift_summary.svg")
    _write_policy_svg(summary, assets_dir / "policy_mode_comparison.svg")
    _write_runtime_governance_svg(summary, assets_dir / "runtime_governance.svg")
    _write_observation_feedback_intake_svg(summary, assets_dir / "observation_feedback_intake.svg")
    _write_provenance_svg(summary, assets_dir / "benchmark_provenance.svg")
    _write_semantic_route_distribution_svg(summary, assets_dir / "semantic_route_distribution.svg")
    _write_semantic_route_performance_svg(summary, assets_dir / "semantic_route_performance.svg")
    _write_content_class_route_performance_svg(summary, assets_dir / "content_class_route_performance.svg")
    _write_recommended_action_distribution_svg(summary, assets_dir / "recommended_action_distribution.svg")
    _write_semantic_route_before_after_svg(summary, assets_dir / "semantic_route_before_after.svg")
    _write_creative_fpr_diagnostic_svg(summary, assets_dir / "creative_fpr_diagnostic.svg")
    _write_bseo_bias_svg(summary, assets_dir / "bseo_bias_profile.svg")
    _write_mutation_atlas_svg(summary, assets_dir / "mutation_bias_atlas.svg")
    _write_lineage_svg(summary, assets_dir / "lineage_overview.svg")

    _write_interactive_dashboards(summary, interactive_dir)

    summary["output_root"] = _relative(root)
    summary["asset_files"] = list(ASSET_FILENAMES)
    summary["interactive_files"] = list(INTERACTIVE_FILENAMES)
    write_json(root / "benchmark_summary.json", summary)
    return summary
