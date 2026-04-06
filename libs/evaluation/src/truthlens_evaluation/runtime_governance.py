from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from truthlens_data_pipeline.paths import read_json, repo_root, utc_now, write_json
from truthlens_model_serving import load_score_events
from truthlens_model_serving.registry import ARCHITECTURE_PLAN_VERSION, HEAD_SPEC_VERSION

DEFAULT_RUNTIME_POLICY = {
    "policy_mode": "bseo-shadow",
    "bseo_min_confidence": 0.58,
    "bseo_max_uncertainty": 0.45,
    "bseo_artifact_max_age_hours": 168.0,
}


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _find_latest_json(directory: Path, suffix: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(
        [path for path in directory.glob(f"*{suffix}") if path.is_file()],
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
            and not path.name.endswith("-bseo-lineage.json")
            and not path.name.endswith("-mutation-bias-atlas.json")
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _artifact_paths() -> dict[str, Path]:
    root = repo_root()
    build_manifest = _read_json_if_exists(root / "datasets" / "manifests" / "builds" / "latest.json") or {}
    model_info = _read_json_if_exists(root / "artifacts" / "trained_models" / "latest" / "model_info.json") or {}
    eval_dir = root / "artifacts" / "eval_runs"
    build_id = str(build_manifest.get("build_id") or model_info.get("build_id") or "").strip()

    eval_report = (
        eval_dir / f"{build_id}.json"
        if build_id and (eval_dir / f"{build_id}.json").exists()
        else _find_latest_eval_report(eval_dir)
    )
    resolved_build_id = build_id or (eval_report.stem if eval_report is not None else "latest")
    return {
        "runtime_policy": root / "configs" / "thresholds" / "runtime-policy.json",
        "bseo_policy": root / "configs" / "thresholds" / "bseo-policy.json",
        "model_info": root / "artifacts" / "trained_models" / "latest" / "model_info.json",
        "eval_report": eval_report or (eval_dir / f"{resolved_build_id}.json"),
        "bseo_report": (
            eval_dir / f"{resolved_build_id}-bseo-report.json"
            if resolved_build_id and (eval_dir / f"{resolved_build_id}-bseo-report.json").exists()
            else _find_latest_json(eval_dir, "-bseo-report.json") or (eval_dir / f"{resolved_build_id}-bseo-report.json")
        ),
        "bseo_lineage": (
            eval_dir / f"{resolved_build_id}-bseo-lineage.json"
            if resolved_build_id and (eval_dir / f"{resolved_build_id}-bseo-lineage.json").exists()
            else _find_latest_json(eval_dir, "-bseo-lineage.json") or (eval_dir / f"{resolved_build_id}-bseo-lineage.json")
        ),
        "mutation_atlas": (
            eval_dir / f"{resolved_build_id}-mutation-bias-atlas.json"
            if resolved_build_id and (eval_dir / f"{resolved_build_id}-mutation-bias-atlas.json").exists()
            else _find_latest_json(eval_dir, "-mutation-bias-atlas.json")
            or (eval_dir / f"{resolved_build_id}-mutation-bias-atlas.json")
        ),
        "summary_latest": root / "artifacts" / "reports" / "runtime-governance-latest.json",
        "summary_build": root / "artifacts" / "reports" / f"{resolved_build_id}-runtime-governance.json",
    }


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


def _normalized_policy_mode(mode: str) -> str:
    if mode == "rl-shadow":
        return "bseo-shadow"
    if mode == "rl-live":
        return "bseo-live"
    return mode


def _artifact_age_hours(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    normalized = timestamp.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0, 3)


def _load_runtime_policy() -> dict[str, Any]:
    payload = _read_json_if_exists(_artifact_paths()["runtime_policy"]) or {}
    merged = DEFAULT_RUNTIME_POLICY.copy()
    merged.update({key: value for key, value in payload.items() if value is not None})
    if "bseo_min_confidence" not in merged and "rl_min_confidence" in merged:
        merged["bseo_min_confidence"] = payload.get("rl_min_confidence")
    if "bseo_max_uncertainty" not in merged and "rl_max_uncertainty" in merged:
        merged["bseo_max_uncertainty"] = payload.get("rl_max_uncertainty")
    if "bseo_artifact_max_age_hours" not in merged and "rl_artifact_max_age_hours" in merged:
        merged["bseo_artifact_max_age_hours"] = payload.get("rl_artifact_max_age_hours")
    merged["policy_mode"] = str(merged.get("policy_mode", "threshold-default"))
    merged["resolved_policy_mode"] = _normalized_policy_mode(str(merged["policy_mode"]))
    merged["bseo_min_confidence"] = _safe_float(merged.get("bseo_min_confidence"), 0.58)
    merged["bseo_max_uncertainty"] = _safe_float(merged.get("bseo_max_uncertainty"), 0.45)
    merged["bseo_artifact_max_age_hours"] = _safe_float(merged.get("bseo_artifact_max_age_hours"), 168.0)
    return merged


def _bseo_artifact_status(
    bseo_policy: dict[str, Any] | None,
    runtime_policy: dict[str, Any],
) -> dict[str, Any]:
    if bseo_policy is None:
        return {
            "available": False,
            "compatible": False,
            "stale": False,
            "status": "missing",
            "reason": "bseo policy artifact is missing",
            "age_hours": None,
            "build_id": None,
            "policy_version": None,
        }
    age_hours = _artifact_age_hours(str(bseo_policy.get("generated_at", "")) or None)
    compatible = (
        str(bseo_policy.get("head_spec_version", "")) == HEAD_SPEC_VERSION
        and str(bseo_policy.get("architecture_plan_version", "")) == ARCHITECTURE_PLAN_VERSION
        and isinstance(bseo_policy.get("control_genome"), dict)
    )
    stale = bool(
        age_hours is not None
        and age_hours > _safe_float(runtime_policy.get("bseo_artifact_max_age_hours"), 168.0)
    )
    status = "compatible"
    reason = None
    if not compatible:
        status = "incompatible"
        reason = "bseo policy artifact contracts do not match the current runtime"
    elif stale:
        status = "stale"
        reason = "bseo policy artifact is older than the allowed runtime age"
    return {
        "available": True,
        "compatible": compatible,
        "stale": stale,
        "status": status,
        "reason": reason,
        "age_hours": age_hours,
        "build_id": bseo_policy.get("build_id"),
        "policy_version": bseo_policy.get("policy_version"),
    }


def _shadow_observation_count() -> int:
    return sum(
        1
        for row in load_score_events()
        if "-shadow" in str(row.get("policy_version", ""))
    )


def build_runtime_governance_summary() -> dict[str, Any]:
    paths = _artifact_paths()
    runtime_policy = _load_runtime_policy()
    build_manifest = _read_json_if_exists(repo_root() / "datasets" / "manifests" / "builds" / "latest.json") or {}
    eval_report = _read_json_if_exists(paths["eval_report"]) or {}
    bseo_policy = _read_json_if_exists(paths["bseo_policy"])
    bseo_report = _read_json_if_exists(paths["bseo_report"]) or {}
    mutation_atlas = _read_json_if_exists(paths["mutation_atlas"]) or {}
    lineage_payload = read_json(paths["bseo_lineage"]) if paths["bseo_lineage"].exists() else []

    artifact_status = _bseo_artifact_status(bseo_policy, runtime_policy)
    sample_count = _safe_int(eval_report.get("sample_count"))
    validation_f1 = _safe_float(dict(eval_report.get("validation_metrics", {})).get("f1"))
    eval_f1 = _safe_float(dict(eval_report.get("metrics", {})).get("f1"))
    validation_gap = round(abs(eval_f1 - validation_f1), 4)
    calibration_error = _safe_float(eval_report.get("calibration_error"))
    best_performance = dict(bseo_report.get("best_performance", {}))
    benign_fpr = _safe_float(best_performance.get("benign_false_positive_rate"))
    objective_score = _safe_float(
        dict(bseo_report.get("objective", {})).get("score", bseo_report.get("best_objective"))
    )
    mutation_status = str(mutation_atlas.get("status", "missing"))
    usable_mutations = _safe_int(mutation_atlas.get("usable_mutations"))
    lineage_count = len(lineage_payload) if isinstance(lineage_payload, list) else 0
    shadow_observation_count = _shadow_observation_count()

    shadow_blockers: list[str] = []
    if not artifact_status["available"]:
        shadow_blockers.append("missing-bseo-artifact")
    if artifact_status["available"] and not artifact_status["compatible"]:
        shadow_blockers.append("incompatible-bseo-artifact")
    if artifact_status["stale"]:
        shadow_blockers.append("stale-bseo-artifact")
    if sample_count < 30:
        shadow_blockers.append("insufficient-eval-sample")
    if not bseo_report:
        shadow_blockers.append("missing-bseo-report")
    if lineage_count < 12:
        shadow_blockers.append("insufficient-lineage-history")
    if mutation_status not in {"sparse", "clustered"}:
        shadow_blockers.append("missing-mutation-atlas")
    if objective_score < 0.65:
        shadow_blockers.append("low-bseo-objective")

    live_blockers = list(shadow_blockers)
    if validation_f1 < 0.8:
        live_blockers.append("validation-f1-below-live-threshold")
    if validation_gap > 0.1:
        live_blockers.append("validation-gap-too-large")
    if calibration_error > 0.25:
        live_blockers.append("calibration-error-too-high")
    if benign_fpr > 0.02:
        live_blockers.append("benign-fpr-too-high")
    if mutation_status != "clustered":
        live_blockers.append("mutation-atlas-not-clustered")
    if usable_mutations < 24:
        live_blockers.append("insufficient-usable-mutations")
    if shadow_observation_count < 200:
        live_blockers.append("insufficient-shadow-observation-history")

    shadow_eligible = not shadow_blockers
    live_eligible = not live_blockers
    recommended_mode = "bseo-shadow" if shadow_eligible else "threshold-default"
    max_promotable_mode = "bseo-live" if live_eligible else recommended_mode

    summary = {
        "generated_at": utc_now(),
        "build_id": build_manifest.get("build_id"),
        "runtime_policy": {
            "configured_mode": runtime_policy["policy_mode"],
            "resolved_mode": runtime_policy["resolved_policy_mode"],
            "bseo_min_confidence": runtime_policy["bseo_min_confidence"],
            "bseo_max_uncertainty": runtime_policy["bseo_max_uncertainty"],
            "bseo_artifact_max_age_hours": runtime_policy["bseo_artifact_max_age_hours"],
        },
        "artifacts": {
            "bseo_policy": artifact_status,
            "lineage_count": lineage_count,
            "mutation_atlas_status": mutation_status,
            "usable_mutations": usable_mutations,
        },
        "dataset": {
            "train_count": _safe_int(dict(build_manifest.get("counts", {})).get("train")),
            "validation_count": _safe_int(dict(build_manifest.get("counts", {})).get("validation")),
            "test_count": _safe_int(dict(build_manifest.get("counts", {})).get("test")),
            "eval_sample_count": sample_count,
        },
        "performance": {
            "eval_f1": eval_f1,
            "validation_f1": validation_f1,
            "validation_gap": validation_gap,
            "calibration_error": calibration_error,
            "bseo_objective_score": objective_score,
            "benign_false_positive_rate": benign_fpr,
            "shadow_observation_count": shadow_observation_count,
        },
        "promotion": {
            "shadow_eligible": shadow_eligible,
            "shadow_blockers": shadow_blockers,
            "live_eligible": live_eligible,
            "live_blockers": live_blockers,
            "recommended_mode": recommended_mode,
            "max_promotable_mode": max_promotable_mode,
        },
    }
    return summary


def persist_runtime_governance_summary(summary: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved_summary = summary or build_runtime_governance_summary()
    paths = _artifact_paths()
    write_json(paths["summary_latest"], resolved_summary)
    write_json(paths["summary_build"], resolved_summary)
    return resolved_summary


def apply_runtime_promotion(*, mode: str = "auto") -> dict[str, Any]:
    summary = persist_runtime_governance_summary()
    requested_mode = mode.strip().lower()
    if requested_mode not in {"auto", "threshold-default", "bseo-shadow", "bseo-live"}:
        raise ValueError(f"Unsupported runtime promotion mode: {mode}")

    promotion = dict(summary["promotion"])
    if requested_mode == "auto":
        target_mode = str(promotion["recommended_mode"])
    else:
        target_mode = requested_mode

    if target_mode == "bseo-shadow" and not bool(promotion["shadow_eligible"]):
        raise ValueError(
            "BSEO shadow promotion is not currently eligible: "
            + ", ".join(str(value) for value in promotion["shadow_blockers"])
        )
    if target_mode == "bseo-live" and not bool(promotion["live_eligible"]):
        raise ValueError(
            "BSEO live promotion is not currently eligible: "
            + ", ".join(str(value) for value in promotion["live_blockers"])
        )

    runtime_policy = _load_runtime_policy()
    updated_policy = {
        "policy_mode": target_mode,
        "bseo_min_confidence": runtime_policy["bseo_min_confidence"],
        "bseo_max_uncertainty": runtime_policy["bseo_max_uncertainty"],
        "bseo_artifact_max_age_hours": runtime_policy["bseo_artifact_max_age_hours"],
        "rl_min_confidence": runtime_policy["bseo_min_confidence"],
        "rl_max_uncertainty": runtime_policy["bseo_max_uncertainty"],
        "rl_artifact_max_age_hours": runtime_policy["bseo_artifact_max_age_hours"],
    }
    write_json(_artifact_paths()["runtime_policy"], updated_policy)
    summary["promotion"]["applied_mode"] = target_mode
    summary["promotion"]["applied_at"] = utc_now()
    summary["runtime_policy"]["configured_mode"] = target_mode
    summary["runtime_policy"]["resolved_mode"] = _normalized_policy_mode(target_mode)
    persist_runtime_governance_summary(summary)
    return summary
