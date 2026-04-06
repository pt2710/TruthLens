from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from truthlens_data_pipeline.paths import ensure_dir, read_json, repo_root, write_json
from truthlens_evaluation.runtime_governance import persist_runtime_governance_summary


ASSET_FILENAMES = (
    "train_validation_eval_overview.svg",
    "per_head_metrics.svg",
    "calibration_error.svg",
    "confusion_matrix_eval.svg",
    "threshold_sweep.svg",
    "drift_summary.svg",
    "policy_mode_comparison.svg",
    "runtime_governance.svg",
    "benchmark_provenance.svg",
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
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


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
    return {
        "model_info": model_info_path if model_info_path.exists() else None,
        "eval_report": eval_report_path,
        "simulation": simulation_path,
        "bseo_report": bseo_report_path,
        "mutation_atlas": mutation_atlas_path,
        "lineage": lineage_path,
        "drift_report": drift_path,
        "runtime_policy": runtime_policy_path if runtime_policy_path.exists() else None,
        "thresholds": threshold_path if threshold_path.exists() else None,
        "bseo_policy": bseo_policy_path if bseo_policy_path.exists() else None,
        "runtime_governance": runtime_governance_path if runtime_governance_path.exists() else None,
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


def build_benchmark_summary() -> dict[str, Any]:
    runtime_governance = persist_runtime_governance_summary()
    paths = _artifact_paths()
    model_info = _read_json_if_exists(paths["model_info"])
    eval_report = _read_json_if_exists(paths["eval_report"])
    simulation = _read_json_if_exists(paths["simulation"])
    drift_report = _read_json_if_exists(paths["drift_report"])
    runtime_policy = _read_json_if_exists(paths["runtime_policy"])
    thresholds = _read_json_if_exists(paths["thresholds"])
    bseo_policy = _read_json_if_exists(paths["bseo_policy"])
    bseo_report = _read_json_if_exists(paths["bseo_report"])
    mutation_atlas = _read_json_if_exists(paths["mutation_atlas"])
    lineage = read_json(paths["lineage"]) if paths["lineage"] is not None and paths["lineage"].exists() else None

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
        "drift": drift_report or {},
        "bseo": {
            "policy_artifact": _summarize_bseo_policy_artifact(bseo_policy),
            "report": _summarize_bseo_report(bseo_report),
            "bias_signature": bseo_bias_signature,
            "mutation_bias_atlas": mutation_atlas_payload,
            "lineage": bseo_lineage_summary,
            "available": bool(bseo_policy or bseo_report or simulation_has_bseo),
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


def _svg_document(title: str, subtitle: str, width: int, height: int, body: list[str]) -> str:
    escaped_title = escape(title)
    escaped_subtitle = escape(subtitle)
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            "<style>",
            "text { font-family: 'Segoe UI', Arial, sans-serif; fill: #0f172a; }",
            ".title { font-size: 24px; font-weight: 700; }",
            ".subtitle { font-size: 12px; fill: #475569; }",
            ".card { fill: #f8fafc; stroke: #cbd5e1; stroke-width: 1.5; rx: 14; }",
            ".accent { fill: #eff6ff; stroke: #93c5fd; stroke-width: 1.5; rx: 14; }",
            ".warn { fill: #fff7ed; stroke: #fdba74; stroke-width: 1.5; rx: 14; }",
            ".label { font-size: 13px; fill: #475569; }",
            ".value { font-size: 28px; font-weight: 700; }",
            ".small { font-size: 11px; fill: #64748b; }",
            ".axis { stroke: #94a3b8; stroke-width: 1; }",
            ".grid { stroke: #e2e8f0; stroke-width: 1; }",
            ".legend { font-size: 12px; fill: #334155; }",
            ".stub { font-size: 16px; font-weight: 600; }",
            "</style>",
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
            f'<text class="title" x="40" y="48">{escaped_title}</text>',
            f'<text class="subtitle" x="40" y="72">{escaped_subtitle}</text>',
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
    lines = [f'<rect class="{accent}" x="{x}" y="{y}" width="{width}" height="{height}" rx="14" />']
    lines.append(f'<text class="label" x="{x + 18}" y="{y + 26}">{escape(label)}</text>')
    lines.append(f'<text class="value" x="{x + 18}" y="{y + 70}">{escape(value)}</text>')
    if note:
        for index, line in enumerate(_wrap_text(note, 52)):
            lines.append(f'<text class="small" x="{x + 18}" y="{y + 98 + index * 16}">{escape(line)}</text>')
    return "\n".join(lines)


def _stub_svg(title: str, subtitle: str, message: str, path: Path) -> None:
    body = [
        '<rect class="warn" x="40" y="112" width="920" height="220" rx="18" />',
        f'<text class="stub" x="72" y="168">{escape("Data unavailable for this visualization")}</text>',
    ]
    for index, line in enumerate(_wrap_text(message, 88)):
        body.append(f'<text class="subtitle" x="72" y="{206 + index * 18}">{escape(line)}</text>')
    path.write_text(_svg_document(title, subtitle, 1000, 380, body), encoding="utf-8")


def _write_overview_svg(summary: dict[str, Any], path: Path) -> None:
    eval_metrics = dict(summary["metrics"]["eval"])
    validation_metrics = dict(summary["metrics"]["validation"])
    cards = [
        _card(40, 112, 290, 150, "Eval F1", _format_metric(_safe_float(eval_metrics.get("f1"))), "Committed eval snapshot"),
        _card(
            355,
            112,
            290,
            150,
            "Validation F1",
            _format_metric(_safe_float(validation_metrics.get("f1"))),
            "Cross-check against validation split",
        ),
        _card(
            670,
            112,
            290,
            150,
            "Eval sample count",
            str(summary.get("sample_count") or "n/a"),
            "Very small n must be treated as unstable",
            "warn" if (summary.get("sample_count") or 0) < 30 else "accent",
        ),
        _card(40, 282, 290, 150, "Eval precision", _format_metric(_safe_float(eval_metrics.get("precision")))),
        _card(355, 282, 290, 150, "Eval recall", _format_metric(_safe_float(eval_metrics.get("recall")))),
        _card(
            670,
            282,
            290,
            150,
            "Validation calibration",
            _format_metric(_safe_float(summary["metrics"]["validation_calibration_error"])),
        ),
    ]
    path.write_text(
        _svg_document(
            "TruthLens benchmark overview",
            "Current committed evaluation and validation snapshot. Training metrics are not published in the current root artifacts.",
            1000,
            470,
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
    width = 1200
    height = 500
    chart_x = 60
    chart_y = 110
    chart_w = 1080
    chart_h = 300
    group_width = chart_w / max(len(categories), 1)
    bar_width = max(18.0, min(48.0, group_width / max(len(series) + 1, 2)))
    body: list[str] = []
    for step in range(6):
        y = chart_y + chart_h - (chart_h * step / 5.0)
        label = f"{(y_max * step / 5.0):.2f}"
        body.append(f'<line class="grid" x1="{chart_x}" y1="{y:.1f}" x2="{chart_x + chart_w}" y2="{y:.1f}" />')
        body.append(f'<text class="small" x="{chart_x - 36}" y="{y + 4:.1f}">{escape(label)}</text>')
    body.append(f'<line class="axis" x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" />')
    body.append(
        f'<line class="axis" x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" />'
    )
    for category_index, category in enumerate(categories):
        group_x = chart_x + category_index * group_width + 20
        for series_index, (_, color, values) in enumerate(series):
            value = values[category_index]
            safe_value = max(0.0, min(value, y_max))
            bar_height = 0.0 if y_max == 0 else (safe_value / y_max) * chart_h
            x = group_x + series_index * (bar_width + 6)
            y = chart_y + chart_h - bar_height
            body.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}" rx="6" />'
            )
        body.append(
            f'<text class="small" x="{group_x + group_width / 4:.1f}" y="{chart_y + chart_h + 24}" text-anchor="middle">{escape(category)}</text>'
        )
    legend_x = chart_x
    for index, (name, color, _) in enumerate(series):
        item_x = legend_x + index * 190
        body.append(f'<rect x="{item_x}" y="438" width="14" height="14" fill="{color}" rx="3" />')
        body.append(f'<text class="legend" x="{item_x + 22}" y="450">{escape(name)}</text>')
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
        y_max=max(max(values, default=0.0), 1.0),
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
            f'<rect x="{x}" y="{y}" width="180" height="90" rx="14" fill="{fill}" stroke="#94a3b8" stroke-width="1.5" />'
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
            640,
            420,
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
    width = 1100
    height = 500
    chart_x = 80
    chart_y = 120
    chart_w = 940
    chart_h = 280
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
        body.append(f'<text class="small" x="{chart_x - 42}" y="{y + 4:.1f}">{step / 5.0:.2f}</text>')
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
            f'<text class="small" x="{x:.1f}" y="{chart_y + chart_h + 24}" text-anchor="middle">{threshold:.2f}</text>'
        )
    body.append('<rect x="80" y="430" width="14" height="14" fill="#2563eb" rx="3" />')
    body.append('<text class="legend" x="102" y="442">F1</text>')
    body.append('<rect x="160" y="430" width="14" height="14" fill="#c2410c" rx="3" />')
    body.append('<text class="legend" x="182" y="442">Normalized intervention cost</text>')
    body.append(f'<text class="small" x="80" y="468">Intervention cost range in source artifact: {cost_min:.3f} to {cost_max:.3f}</text>')
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
    metrics = [
        ("Title length shift", _safe_float(drift.get("title_length_shift"))),
        ("Sensational count shift", _safe_float(drift.get("sensational_count_shift"))),
        ("Label rate shift", _safe_float(drift.get("label_rate_shift"))),
    ]
    width = 960
    height = 430
    chart_x = 120
    chart_y = 120
    chart_w = 760
    chart_h = 200
    max_abs = max(abs(value) for _, value in metrics) or 1.0
    body: list[str] = []
    zero_x = chart_x + chart_w / 2
    body.append(f'<line class="axis" x1="{zero_x}" y1="{chart_y}" x2="{zero_x}" y2="{chart_y + chart_h}" />')
    for index, (label, value) in enumerate(metrics):
        y = chart_y + 24 + index * 58
        span = (abs(value) / max_abs) * (chart_w / 2 - 40)
        if value >= 0:
            x = zero_x
            width_value = span
            color = "#2563eb"
        else:
            x = zero_x - span
            width_value = span
            color = "#c2410c"
        body.append(f'<text class="label" x="40" y="{y + 18}">{escape(label)}</text>')
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width_value:.1f}" height="28" fill="{color}" rx="8" />')
        body.append(f'<text class="small" x="{zero_x + 10}" y="{y + 18}">{value:.3f}</text>')
    body.append(
        f'<text class="small" x="40" y="372">Reference rows: {_safe_int(drift.get("reference_count"))} | Current rows: {_safe_int(drift.get("current_count"))}</text>'
    )
    path.write_text(
        _svg_document(
            "Drift summary",
            "Signed shifts from the committed drift report. Small current samples limit interpretability.",
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
            40,
            112,
            280,
            150,
            "Configured runtime mode",
            str(runtime.get("configured_policy_mode", "n/a")),
            "Directly from configs/thresholds/runtime-policy.json",
            "accent",
        ),
        _card(
            350,
            112,
            280,
            150,
            "Resolved runtime mode",
            str(runtime.get("resolved_policy_mode", "n/a")),
            "Aliases normalized for architectural truth",
        ),
        _card(
            660,
            112,
            300,
            150,
            "Committed BSEO artifact",
            "yes" if runtime.get("bseo_artifact_committed") else "no",
            "If absent, shadow/live is code-supported but not promoted as a committed runtime artifact.",
            "warn" if not runtime.get("bseo_artifact_committed") else "accent",
        ),
        _card(
            40,
            282,
            280,
            140,
            "Selective verification",
            "explicit",
            "Selective deep verification exists as a separate contract layer rather than a mandatory hot path.",
        ),
        _card(
            350,
            282,
            280,
            140,
            "Heavy LLM in hot path",
            "no",
            "Gemini/manual-report flows stay downstream of baseline scoring.",
        ),
    ]
    path.write_text(
        _svg_document(
            "Policy mode and runtime eligibility",
            "This panel is derived from committed runtime config and artifact presence, not from aspirational docs.",
            1000,
            470,
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
            40,
            112,
            280,
            150,
            "Recommended mode",
            str(promotion.get("recommended_mode", "n/a")),
            "The highest runtime mode currently justified by committed artifacts and guardrails.",
            "accent" if str(promotion.get("recommended_mode", "")) != "threshold-default" else "warn",
        ),
        _card(
            350,
            112,
            280,
            150,
            "Max promotable mode",
            str(promotion.get("max_promotable_mode", "n/a")),
            "Live is only eligible after calibration, lineage, atlas, and shadow-soak checks pass.",
        ),
        _card(
            660,
            112,
            300,
            150,
            "Current eval footprint",
            f"test={_safe_int(dataset.get('test_count'))} | eval={_safe_int(dataset.get('eval_sample_count'))}",
            "Governance summaries are only credible when dataset counts are large enough to matter.",
        ),
        _card(
            40,
            282,
            280,
            150,
            "Objective + calibration",
            f"obj={_safe_float(performance.get('bseo_objective_score')):.3f} | ece={_safe_float(performance.get('calibration_error')):.3f}",
            "BSEO promotion stays downstream of fused/calibrated scoring quality.",
        ),
        _card(
            350,
            282,
            280,
            150,
            "Atlas + lineage",
            f"{artifacts.get('mutation_atlas_status', 'n/a')} | lineage={_safe_int(artifacts.get('lineage_count'))}",
            f"usable_mutations={_safe_int(artifacts.get('usable_mutations'))}",
        ),
        _card(
            660,
            282,
            300,
            150,
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
            1000,
            470,
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
        _card(40, 112, 290, 150, "Build ID", build_id, "Artifact lineage anchor"),
        _card(355, 112, 290, 150, "Model version", model_version, "Snapshot from trained model info"),
        _card(670, 112, 290, 150, "Eval sample count", sample_count, "Committed evaluation sample size"),
        _card(
            40,
            282,
            920,
            140,
            "Artifact timestamps",
            "committed",
            f"model_info={timestamps.get('model_info')} | eval={timestamps.get('eval_report')} | drift={timestamps.get('drift_report')}",
        ),
        _card(
            40,
            442,
            920,
            140,
            "Training timestamp",
            trained_at,
            "If this timestamp and current docs diverge, the docs are stale.",
        ),
    ]
    path.write_text(
        _svg_document(
            "Benchmark provenance",
            "Every benchmark claim in README should trace back to these committed artifacts.",
            1000,
            620,
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
        _card(40, 112, 280, 150, "Atlas status", status),
        _card(350, 112, 280, 150, "Usable mutations", str(_safe_int(atlas.get("usable_mutations")))),
        _card(660, 112, 280, 150, "Cluster count", str(len(clusters))),
    ]
    for index, cluster in enumerate(clusters[:3]):
        body.append(
            _card(
                40 + index * 310,
                282,
                280,
                150,
                f"Cluster {cluster.get('cluster_id')}",
                f"size={_safe_int(cluster.get('size'))}",
                f"avg dF={_safe_float(cluster.get('average_delta_f')):.3f}, avg dB={_safe_float(cluster.get('average_delta_b')):.3f}",
            )
        )
    path.write_text(
        _svg_document(
            "Mutation bias atlas",
            "Cluster overview from committed BSEO lineage artifacts.",
            1000,
            470,
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
        y_max=max(max(objective, default=0.0), 1.0),
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
        "## Runtime Governance",
        "",
        f"- Shadow eligible: `{promotion.get('shadow_eligible', False)}`",
        f"- Live eligible: `{promotion.get('live_eligible', False)}`",
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
      body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
      h1, h2 {{ margin-top: 0; }}
      .card {{ background: white; border: 1px solid #cbd5e1; border-radius: 16px; padding: 18px; margin-bottom: 18px; }}
      code, pre {{ background: #0f172a; color: #e2e8f0; border-radius: 10px; padding: 12px; overflow: auto; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }}
      th {{ background: #eff6ff; }}
      .warn {{ background: #fff7ed; border-color: #fdba74; }}
      .muted {{ color: #475569; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>{escape(title)}</h1>
      <p class="muted">Generated from committed artifacts. This page is static and deterministic.</p>
    </div>
    {body_html}
    <div class="card">
      <h2>Embedded summary payload</h2>
      <pre>{escape(payload)}</pre>
    </div>
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
          <p><strong>Build ID:</strong> {escape(str(summary.get('build_id') or 'n/a'))}</p>
          <p><strong>Eval sample count:</strong> {escape(str(summary.get('sample_count') or 'n/a'))}</p>
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
          <p><strong>Configured mode:</strong> {escape(str(summary['runtime_truth']['configured_policy_mode']))}</p>
          <p><strong>Resolved mode:</strong> {escape(str(summary['runtime_truth']['resolved_policy_mode']))}</p>
          <p><strong>Recommended mode:</strong> {escape(str(summary['runtime_truth']['recommended_policy_mode']))}</p>
          <p><strong>Max promotable mode:</strong> {escape(str(summary['runtime_truth']['max_promotable_mode']))}</p>
          <p><strong>Committed BSEO artifact:</strong> {escape('yes' if summary['runtime_truth']['bseo_artifact_committed'] else 'no')}</p>
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
          <p><strong>Status:</strong> {escape(str(atlas.get('status', 'missing')))}</p>
          <p><strong>Usable mutations:</strong> {escape(str(_safe_int(atlas.get('usable_mutations'))))}</p>
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
          <p><strong>Configured mode:</strong> {escape(str(summary['runtime_truth']['configured_policy_mode']))}</p>
          <p><strong>Recommended mode:</strong> {escape(str(promotion.get('recommended_mode', 'n/a')))}</p>
          <p><strong>Max promotable mode:</strong> {escape(str(promotion.get('max_promotable_mode', 'n/a')))}</p>
          <p><strong>Shadow eligible:</strong> {escape(str(promotion.get('shadow_eligible', False)))}</p>
          <p><strong>Live eligible:</strong> {escape(str(promotion.get('live_eligible', False)))}</p>
        </div>
        <div class="card">
          <h2>Observed runtime evidence</h2>
          <p><strong>Shadow observations:</strong> {escape(str(_safe_int(dict(governance.get('performance', {})).get('shadow_observation_count'))))}</p>
          <p><strong>Eval sample count:</strong> {escape(str(_safe_int(dict(governance.get('dataset', {})).get('eval_sample_count'))))}</p>
          <p><strong>Mutation atlas status:</strong> {escape(str(dict(governance.get('artifacts', {})).get('mutation_atlas_status', 'n/a')))}</p>
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


def render_benchmark_bundle(output_root: Path | None = None) -> dict[str, Any]:
    root = output_root or (repo_root() / "docs" / "benchmarks" / "latest")
    assets_dir = ensure_dir(root / "assets")
    interactive_dir = ensure_dir(root / "interactive")

    summary = build_benchmark_summary()
    write_json(root / "benchmark_summary.json", summary)
    (root / "benchmark_summary.md").write_text(_benchmark_summary_markdown(summary), encoding="utf-8")
    (assets_dir / "overall_metrics_table.md").write_text(_overall_metrics_table(summary), encoding="utf-8")

    _write_overview_svg(summary, assets_dir / "train_validation_eval_overview.svg")
    _write_per_head_svg(summary, assets_dir / "per_head_metrics.svg")
    _write_calibration_svg(summary, assets_dir / "calibration_error.svg")
    _write_confusion_svg(summary, assets_dir / "confusion_matrix_eval.svg")
    _write_threshold_sweep_svg(summary, assets_dir / "threshold_sweep.svg")
    _write_drift_svg(summary, assets_dir / "drift_summary.svg")
    _write_policy_svg(summary, assets_dir / "policy_mode_comparison.svg")
    _write_runtime_governance_svg(summary, assets_dir / "runtime_governance.svg")
    _write_provenance_svg(summary, assets_dir / "benchmark_provenance.svg")
    _write_bseo_bias_svg(summary, assets_dir / "bseo_bias_profile.svg")
    _write_mutation_atlas_svg(summary, assets_dir / "mutation_bias_atlas.svg")
    _write_lineage_svg(summary, assets_dir / "lineage_overview.svg")

    _write_interactive_dashboards(summary, interactive_dir)

    summary["output_root"] = _relative(root)
    summary["asset_files"] = list(ASSET_FILENAMES)
    summary["interactive_files"] = list(INTERACTIVE_FILENAMES)
    write_json(root / "benchmark_summary.json", summary)
    return summary
