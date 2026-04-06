from __future__ import annotations

from copy import deepcopy
from random import Random
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from truthlens_feature_extractors import BENIGN_CONTENT_CLASSES, CONTENT_CLASSES, FACTUAL_CONTENT_CLASSES

from .metrics import compute_binary_metrics, expected_calibration_error

THRESHOLD_NAMES = (
    "badge_threshold",
    "blur_threshold",
    "report_prompt_threshold",
    "hide_threshold",
)

BIAS_NAMES = (
    "sensational_weight",
    "crossmodal_rigidity",
    "channel_prior_dependency",
    "genre_confusion",
    "uncertainty_calibration",
)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _round(value: float) -> float:
    return round(float(value), 4)


def _default_thresholds() -> dict[str, float]:
    return {
        "badge_threshold": 0.35,
        "blur_threshold": 0.60,
        "report_prompt_threshold": 0.80,
        "hide_threshold": 0.93,
    }


def _default_control_genome(seed_thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    thresholds = deepcopy(seed_thresholds or _default_thresholds())
    return {
        "global_thresholds": thresholds,
        "content_threshold_offsets": {
            "news": -0.03,
            "commentary": -0.01,
            "documentary": -0.02,
            "music": 0.08,
            "art": 0.06,
            "satire": 0.04,
            "gaming": 0.03,
            "promo": -0.03,
            "unknown": 0.0,
        },
        "mismatch_weight_by_class": {
            "news": 1.15,
            "commentary": 1.05,
            "documentary": 1.12,
            "music": 0.7,
            "art": 0.78,
            "satire": 0.88,
            "gaming": 0.92,
            "promo": 1.08,
            "unknown": 1.0,
        },
        "sensational_weight_by_class": {
            "news": 1.1,
            "commentary": 1.02,
            "documentary": 1.05,
            "music": 0.82,
            "art": 0.84,
            "satire": 0.9,
            "gaming": 0.95,
            "promo": 1.12,
            "unknown": 1.0,
        },
        "channel_prior_temperature": 1.0,
        "uncertainty_escalation_bias": 1.0,
    }


def _flatten_genome(theta: dict[str, Any]) -> dict[str, float]:
    flattened: dict[str, float] = {}
    for threshold_name in THRESHOLD_NAMES:
        flattened[f"global.{threshold_name}"] = float(theta["global_thresholds"][threshold_name])
    for content_class in CONTENT_CLASSES:
        flattened[f"offset.{content_class}"] = float(theta["content_threshold_offsets"].get(content_class, 0.0))
    for content_class in CONTENT_CLASSES:
        flattened[f"mismatch.{content_class}"] = float(theta["mismatch_weight_by_class"].get(content_class, 1.0))
    for content_class in CONTENT_CLASSES:
        flattened[f"sensational.{content_class}"] = float(
            theta["sensational_weight_by_class"].get(content_class, 1.0)
        )
    flattened["channel_prior_temperature"] = float(theta.get("channel_prior_temperature", 1.0))
    flattened["uncertainty_escalation_bias"] = float(theta.get("uncertainty_escalation_bias", 1.0))
    return flattened


def _normalize_thresholds(thresholds: dict[str, float]) -> dict[str, float]:
    badge = _clip(float(thresholds["badge_threshold"]), 0.15, 0.55)
    blur = _clip(max(badge + 0.08, float(thresholds["blur_threshold"])), 0.3, 0.82)
    report = _clip(max(blur + 0.08, float(thresholds["report_prompt_threshold"])), 0.5, 0.94)
    hide = _clip(max(report + 0.06, float(thresholds["hide_threshold"])), 0.7, 0.99)
    return {
        "badge_threshold": _round(badge),
        "blur_threshold": _round(blur),
        "report_prompt_threshold": _round(report),
        "hide_threshold": _round(hide),
    }


def _thresholds_for_class(theta: dict[str, Any], content_class: str) -> dict[str, float]:
    resolved_class = content_class if content_class in CONTENT_CLASSES else "unknown"
    offset = float(theta["content_threshold_offsets"].get(resolved_class, 0.0))
    thresholds = {
        threshold_name: float(theta["global_thresholds"][threshold_name]) + offset
        for threshold_name in THRESHOLD_NAMES
    }
    return _normalize_thresholds(thresholds)


def _resolve_action(score: float, thresholds: dict[str, float]) -> str:
    if score < thresholds["badge_threshold"]:
        return "none"
    if score < thresholds["blur_threshold"]:
        return "badge"
    if score < thresholds["report_prompt_threshold"]:
        return "blur"
    if score < thresholds["hide_threshold"]:
        return "ask-report"
    return "hide"


def _row_bias_metrics(row: dict[str, Any]) -> dict[str, float]:
    payload = row.get("bias_primitives", {})
    return {
        name: float(payload.get(name, 0.0))
        for name in BIAS_NAMES
    }


def _row_content_class(row: dict[str, Any]) -> str:
    content_class = str(row.get("content_class", "unknown"))
    return content_class if content_class in CONTENT_CLASSES else "unknown"


def _row_policy_score(row: dict[str, Any], theta: dict[str, Any]) -> tuple[float, float]:
    content_class = _row_content_class(row)
    bias_metrics = _row_bias_metrics(row)
    base_score = float(row.get("score", 0.0))
    mismatch_signal = float(row.get("transcript_mismatch_score", 0.0))
    sensational_signal = _clip(float(row.get("sensational_count", 0.0)) / 4.0, 0.0, 1.0)
    channel_signal = bias_metrics["channel_prior_dependency"]
    uncertainty_signal = float(row.get("uncertainty", 0.0))
    class_confidence = float(row.get("content_class_confidence", 0.0))

    mismatch_weight = float(theta["mismatch_weight_by_class"].get(content_class, 1.0))
    sensational_weight = float(theta["sensational_weight_by_class"].get(content_class, 1.0))
    channel_temperature = float(theta.get("channel_prior_temperature", 1.0))
    uncertainty_bias = float(theta.get("uncertainty_escalation_bias", 1.0))

    policy_score = (
        base_score
        + mismatch_signal * 0.14 * mismatch_weight
        + sensational_signal * 0.1 * sensational_weight
        + channel_signal * 0.08 * channel_temperature
        + uncertainty_signal * 0.06 * uncertainty_bias
    )
    if content_class in BENIGN_CONTENT_CLASSES and class_confidence >= 0.65:
        policy_score -= 0.04
    elif content_class in FACTUAL_CONTENT_CLASSES:
        policy_score += 0.03
    if content_class == "satire" and class_confidence < 0.72:
        policy_score += 0.02
    ablated_policy_score = (
        base_score
        + mismatch_signal * 0.14 * mismatch_weight
        + sensational_signal * 0.1 * sensational_weight
        + uncertainty_signal * 0.06 * uncertainty_bias
    )
    return _clip(policy_score, 0.0, 1.0), _clip(ablated_policy_score, 0.0, 1.0)


def _candidate_outcomes(rows: list[dict[str, Any]], theta: dict[str, Any]) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for row in rows:
        content_class = _row_content_class(row)
        thresholds = _thresholds_for_class(theta, content_class)
        policy_score, ablated_policy_score = _row_policy_score(row, theta)
        action = _resolve_action(policy_score, thresholds)
        outcomes.append(
            {
                "content_class": content_class,
                "label": int(row.get("label", 0)),
                "policy_score": _round(policy_score),
                "ablated_policy_score": _round(ablated_policy_score),
                "predicted_positive": action != "none",
                "action": action,
                "uncertainty": _round(float(row.get("uncertainty", 0.0))),
            }
        )
    return outcomes


def _binary_f1(labels: list[int], predictions: list[int]) -> float:
    if not labels:
        return 0.0
    if len(set(labels)) < 2:
        return 1.0 if labels == predictions else 0.0
    return float(compute_binary_metrics(labels, [float(value) for value in predictions], threshold=0.5)["f1"])


def _slice_performance(
    rows: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    by_class: dict[str, dict[str, float]] = {}
    for content_class in CONTENT_CLASSES:
        labels = [
            int(outcome["label"])
            for outcome in outcomes
            if str(outcome["content_class"]) == content_class
        ]
        scores = [
            float(outcome["policy_score"])
            for outcome in outcomes
            if str(outcome["content_class"]) == content_class
        ]
        predictions = [
            int(bool(outcome["predicted_positive"]))
            for outcome in outcomes
            if str(outcome["content_class"]) == content_class
        ]
        if not labels:
            continue
        metrics = compute_binary_metrics(labels, scores, threshold=0.5)
        by_class[content_class] = {
            "f1": _round(_binary_f1(labels, predictions)),
            "false_positive_rate": _round(float(metrics["false_positive_rate"])),
            "ece": _round(expected_calibration_error(labels, scores)),
            "coverage": float(len(labels)),
            "intervention_rate": _round(sum(predictions) / max(len(predictions), 1)),
        }
    return by_class


def _candidate_bias_signature(
    rows: list[dict[str, Any]],
    theta: dict[str, Any],
) -> dict[str, Any]:
    by_class: dict[str, dict[str, float]] = {}
    for content_class in CONTENT_CLASSES:
        slice_rows = [row for row in rows if _row_content_class(row) == content_class]
        if not slice_rows:
            continue
        bias_summaries: dict[str, float] = {}
        for bias_name in BIAS_NAMES:
            values: list[float] = []
            for row in slice_rows:
                base_value = float(_row_bias_metrics(row)[bias_name])
                if bias_name == "sensational_weight":
                    adjusted = base_value * float(theta["sensational_weight_by_class"].get(content_class, 1.0))
                elif bias_name == "crossmodal_rigidity":
                    adjusted = base_value * float(theta["mismatch_weight_by_class"].get(content_class, 1.0))
                elif bias_name == "channel_prior_dependency":
                    adjusted = base_value * float(theta.get("channel_prior_temperature", 1.0))
                elif bias_name == "uncertainty_calibration":
                    adjusted = base_value + abs(float(theta.get("uncertainty_escalation_bias", 1.0)) - 1.0) * 0.05
                else:
                    adjusted = base_value
                values.append(_clip(adjusted, 0.0, 1.0))
            bias_summaries[bias_name] = _round(sum(values) / max(len(values), 1))
        by_class[content_class] = bias_summaries

    macro = {
        bias_name: _round(
            sum(values[bias_name] for values in by_class.values()) / max(len(by_class), 1)
        )
        for bias_name in BIAS_NAMES
    }
    negative_bias_score = _round(
        (
            macro["channel_prior_dependency"]
            + macro["genre_confusion"]
            + macro["uncertainty_calibration"]
            + max(macro["crossmodal_rigidity"] - 0.55, 0.0)
            + max(macro["sensational_weight"] - 0.55, 0.0)
        )
        / 5.0
    )
    return {
        "per_class": by_class,
        "macro": macro,
        "negative_bias_score": negative_bias_score,
    }


def _candidate_performance(
    rows: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    slice_metrics = _slice_performance(rows, outcomes)
    factual_f1_values = [
        slice_metrics[content_class]["f1"]
        for content_class in FACTUAL_CONTENT_CLASSES
        if content_class in slice_metrics
    ]
    benign_fpr_values = [
        slice_metrics[content_class]["false_positive_rate"]
        for content_class in BENIGN_CONTENT_CLASSES
        if content_class in slice_metrics
    ]
    calibration_values = [
        slice_metrics[content_class]["ece"]
        for content_class in CONTENT_CLASSES
        if content_class in slice_metrics
    ]
    clean_rows = [
        outcome
        for outcome in outcomes
        if int(outcome["label"]) == 0
    ]
    channel_lock_in = _round(
        sum(
            abs(float(outcome["policy_score"]) - float(outcome["ablated_policy_score"]))
            for outcome in clean_rows
        )
        / max(len(clean_rows), 1)
    )
    genre_confusion = _round(
        sum(
            float(_row_bias_metrics(row)["genre_confusion"])
            for row in rows
        )
        / max(len(rows), 1)
    )
    intervention_rate = _round(
        sum(1 for outcome in outcomes if bool(outcome["predicted_positive"])) / max(len(outcomes), 1)
    )
    return {
        "slice_metrics": slice_metrics,
        "detection_quality": _round(sum(factual_f1_values) / max(len(factual_f1_values), 1)),
        "benign_false_positive_rate": _round(sum(benign_fpr_values) / max(len(benign_fpr_values), 1)),
        "context_sensitivity": _round(1.0 - (sum(benign_fpr_values) / max(len(benign_fpr_values), 1))),
        "macro_ece": _round(sum(calibration_values) / max(len(calibration_values), 1)),
        "calibration": _round(1.0 - (sum(calibration_values) / max(len(calibration_values), 1))),
        "channel_lock_in": channel_lock_in,
        "genre_confusion": genre_confusion,
        "intervention_rate": intervention_rate,
        "action_counts": {
            action_name: sum(1 for outcome in outcomes if outcome["action"] == action_name)
            for action_name in ["none", "badge", "blur", "ask-report", "hide"]
        },
    }


def _rejection_reasons(
    performance: dict[str, Any],
    baseline_performance: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if performance["benign_false_positive_rate"] - baseline_performance["benign_false_positive_rate"] > 0.02:
        reasons.append("benign-fpr-regression")
    if performance["macro_ece"] - baseline_performance["macro_ece"] > 0.02:
        reasons.append("macro-ece-regression")
    if performance["intervention_rate"] - baseline_performance["intervention_rate"] > 0.05:
        reasons.append("intervention-rate-regression")
    return reasons


def _candidate_report(
    rows: list[dict[str, Any]],
    theta: dict[str, Any],
    *,
    baseline_report: dict[str, Any],
    parent_report: dict[str, Any] | None,
) -> dict[str, Any]:
    outcomes = _candidate_outcomes(rows, theta)
    performance = _candidate_performance(rows, outcomes)
    bias_signature = _candidate_bias_signature(rows, theta)
    parent_negative_bias = (
        float(parent_report["bias_signature"]["negative_bias_score"]) if parent_report is not None else 0.0
    )
    delta_detection_quality = (
        performance["detection_quality"] - float(parent_report["performance"]["detection_quality"])
        if parent_report is not None
        else 0.0
    )
    delta_negative_bias = (
        bias_signature["negative_bias_score"] - parent_negative_bias
        if parent_report is not None
        else 0.0
    )
    mutation_stability = 1.0 if parent_report is None or (delta_detection_quality >= 0.0 and delta_negative_bias <= 0.0) else 0.0
    rejection_reasons = _rejection_reasons(performance, baseline_report["performance"])
    accepted = not rejection_reasons
    objective = _round(
        performance["detection_quality"] * 0.45
        + performance["context_sensitivity"] * 0.20
        + performance["calibration"] * 0.15
        + mutation_stability * 0.10
        - performance["channel_lock_in"] * 0.05
        - performance["genre_confusion"] * 0.05
    )
    if not accepted:
        objective = _round(objective - 0.4)
    baseline_slices = baseline_report["performance"]["slice_metrics"]
    slice_deltas = {
        content_class: {
            "f1_delta": _round(
                performance["slice_metrics"].get(content_class, {}).get("f1", 0.0)
                - baseline_slices.get(content_class, {}).get("f1", 0.0)
            ),
            "false_positive_rate_delta": _round(
                performance["slice_metrics"].get(content_class, {}).get("false_positive_rate", 0.0)
                - baseline_slices.get(content_class, {}).get("false_positive_rate", 0.0)
            ),
            "intervention_rate_delta": _round(
                performance["slice_metrics"].get(content_class, {}).get("intervention_rate", 0.0)
                - baseline_slices.get(content_class, {}).get("intervention_rate", 0.0)
            ),
        }
        for content_class in CONTENT_CLASSES
        if content_class in performance["slice_metrics"] or content_class in baseline_slices
    }
    return {
        "theta": theta,
        "performance": performance,
        "bias_signature": bias_signature,
        "objective": objective,
        "mutation_stability": _round(mutation_stability),
        "accepted": accepted,
        "rejection_reasons": rejection_reasons,
        "delta_f": _round(delta_detection_quality),
        "delta_b": _round(delta_negative_bias),
        "slice_deltas": slice_deltas,
    }


def _mutate_genome(theta: dict[str, Any], rng: Random) -> dict[str, Any]:
    child = deepcopy(theta)
    for threshold_name in THRESHOLD_NAMES:
        child["global_thresholds"][threshold_name] = _clip(
            float(child["global_thresholds"][threshold_name]) + rng.uniform(-0.02, 0.02),
            0.15,
            0.99,
        )
    child["global_thresholds"] = _normalize_thresholds(child["global_thresholds"])
    for section_name, low, high in [
        ("content_threshold_offsets", -0.12, 0.12),
        ("mismatch_weight_by_class", 0.6, 1.3),
        ("sensational_weight_by_class", 0.7, 1.3),
    ]:
        mutated_classes = rng.sample(list(CONTENT_CLASSES), k=3)
        for content_class in mutated_classes:
            child[section_name][content_class] = _round(
                _clip(
                    float(child[section_name][content_class]) + rng.uniform(-0.06, 0.06),
                    low,
                    high,
                )
            )
    child["channel_prior_temperature"] = _round(
        _clip(float(child["channel_prior_temperature"]) + rng.uniform(-0.08, 0.08), 0.55, 1.35)
    )
    child["uncertainty_escalation_bias"] = _round(
        _clip(float(child["uncertainty_escalation_bias"]) + rng.uniform(-0.08, 0.08), 0.65, 1.35)
    )
    return child


def _crossover_genome(parent_a: dict[str, Any], parent_b: dict[str, Any], rng: Random) -> dict[str, Any]:
    child = _default_control_genome()
    for threshold_name in THRESHOLD_NAMES:
        child["global_thresholds"][threshold_name] = _round(
            (
                float(parent_a["global_thresholds"][threshold_name])
                + float(parent_b["global_thresholds"][threshold_name])
            )
            / 2.0
            + rng.uniform(-0.01, 0.01)
        )
    child["global_thresholds"] = _normalize_thresholds(child["global_thresholds"])
    for section_name in [
        "content_threshold_offsets",
        "mismatch_weight_by_class",
        "sensational_weight_by_class",
    ]:
        for content_class in CONTENT_CLASSES:
            child[section_name][content_class] = _round(
                (
                    float(parent_a[section_name][content_class])
                    + float(parent_b[section_name][content_class])
                )
                / 2.0
            )
    child["channel_prior_temperature"] = _round(
        (float(parent_a["channel_prior_temperature"]) + float(parent_b["channel_prior_temperature"])) / 2.0
    )
    child["uncertainty_escalation_bias"] = _round(
        (float(parent_a["uncertainty_escalation_bias"]) + float(parent_b["uncertainty_escalation_bias"])) / 2.0
    )
    return _mutate_genome(child, rng)


def _gene_deltas(child_theta: dict[str, Any], parent_thetas: list[dict[str, Any]]) -> dict[str, float]:
    child_flat = _flatten_genome(child_theta)
    parent_flats = [_flatten_genome(theta) for theta in parent_thetas]
    deltas: dict[str, float] = {}
    for key, value in child_flat.items():
        baseline = sum(parent[key] for parent in parent_flats) / max(len(parent_flats), 1)
        deltas[key] = _round(value - baseline)
    return deltas


def _mutation_bias_atlas(lineage_logs: list[dict[str, Any]]) -> dict[str, Any]:
    usable_logs = [log for log in lineage_logs if log.get("accepted")]
    if len(usable_logs) < 12:
        return {
            "status": "sparse",
            "usable_mutations": len(usable_logs),
            "clusters": [],
        }

    matrix: list[list[float]] = []
    gene_keys = sorted(usable_logs[0]["gene_deltas"].keys())
    for log in usable_logs:
        matrix.append(
            [float(log["gene_deltas"][key]) for key in gene_keys]
            + [float(log["delta_f"]), float(log["delta_b"])]
        )
    scaled = StandardScaler().fit_transform(np.asarray(matrix, dtype=float))
    labels = DBSCAN(eps=1.15, min_samples=2).fit_predict(scaled)
    clusters: list[dict[str, Any]] = []
    for cluster_id in sorted(set(labels.tolist())):
        if cluster_id == -1:
            continue
        members = [log for log, label in zip(usable_logs, labels.tolist(), strict=True) if label == cluster_id]
        avg_delta_f = sum(float(member["delta_f"]) for member in members) / max(len(members), 1)
        avg_delta_b = sum(float(member["delta_b"]) for member in members) / max(len(members), 1)
        avg_theta_shift = sum(
            sum(abs(float(value)) for value in member["gene_deltas"].values()) / max(len(member["gene_deltas"]), 1)
            for member in members
        ) / max(len(members), 1)
        clusters.append(
            {
                "cluster_id": int(cluster_id),
                "size": len(members),
                "member_ids": [str(member["candidate_id"]) for member in members],
                "average_delta_f": _round(avg_delta_f),
                "average_delta_b": _round(avg_delta_b),
                "average_theta_shift": _round(avg_theta_shift),
            }
        )
    return {
        "status": "clustered",
        "usable_mutations": len(usable_logs),
        "clusters": clusters,
    }


def run_bseo_search(
    rows: list[dict[str, Any]],
    *,
    seed_thresholds: dict[str, float] | None = None,
    population_size: int = 18,
    generations: int = 7,
    seed: int = 42,
) -> dict[str, Any]:
    rng = Random(seed)
    root_theta = _default_control_genome(seed_thresholds)
    baseline_report = _candidate_report(rows, root_theta, baseline_report={"performance": _candidate_performance(rows, _candidate_outcomes(rows, root_theta))}, parent_report=None)
    baseline_report["candidate_id"] = "g0-root"
    baseline_report["generation"] = 0
    baseline_report["theta"] = root_theta
    baseline_report["bias_signature"] = _candidate_bias_signature(rows, root_theta)
    baseline_report["objective"] = _round(
        baseline_report["performance"]["detection_quality"] * 0.45
        + baseline_report["performance"]["context_sensitivity"] * 0.20
        + baseline_report["performance"]["calibration"] * 0.15
        + 0.10
        - baseline_report["performance"]["channel_lock_in"] * 0.05
        - baseline_report["performance"]["genre_confusion"] * 0.05
    )
    baseline_report["mutation_stability"] = 1.0
    baseline_report["accepted"] = True
    baseline_report["rejection_reasons"] = []
    baseline_report["delta_f"] = 0.0
    baseline_report["delta_b"] = 0.0

    population_specs = [
        {
            "candidate_id": baseline_report["candidate_id"],
            "generation": 0,
            "theta": root_theta,
            "parent_ids": [],
            "mutation_type": "root",
        }
    ]
    for index in range(max(population_size - 1, 1)):
        population_specs.append(
            {
                "candidate_id": f"g0-m{index}",
                "generation": 0,
                "theta": _mutate_genome(root_theta, rng),
                "parent_ids": [baseline_report["candidate_id"]],
                "mutation_type": "mutation",
            }
        )

    lineage_logs: list[dict[str, Any]] = []
    best_candidate = baseline_report
    history: list[dict[str, Any]] = []
    known_reports: dict[str, dict[str, Any]] = {baseline_report["candidate_id"]: baseline_report}

    for generation in range(generations):
        candidate_reports: list[dict[str, Any]] = []
        for spec in population_specs:
            if spec["candidate_id"] == baseline_report["candidate_id"] and generation == 0:
                report = baseline_report
            else:
                parent_reports = [known_reports.get(parent_id, best_candidate) for parent_id in spec["parent_ids"]]
                parent_report = parent_reports[0] if parent_reports else baseline_report
                report = _candidate_report(rows, spec["theta"], baseline_report=baseline_report, parent_report=parent_report)
                report["candidate_id"] = spec["candidate_id"]
                report["generation"] = generation
                report["parent_ids"] = spec["parent_ids"]
                report["mutation_type"] = spec["mutation_type"]
                report["theta"] = spec["theta"]
            candidate_reports.append(report)
            known_reports[report["candidate_id"]] = report
            if spec["parent_ids"]:
                parent_thetas = [known_reports.get(parent_id, baseline_report)["theta"] for parent_id in spec["parent_ids"]]
                lineage_logs.append(
                    {
                        "candidate_id": report["candidate_id"],
                        "generation": generation,
                        "parent_ids": spec["parent_ids"],
                        "mutation_type": spec["mutation_type"],
                        "accepted": bool(report["accepted"]),
                        "objective": _round(report["objective"]),
                        "delta_f": _round(report["delta_f"]),
                        "delta_b": _round(report["delta_b"]),
                        "rejection_reasons": report["rejection_reasons"],
                        "gene_deltas": _gene_deltas(report["theta"], parent_thetas),
                        "slice_deltas": report["slice_deltas"],
                    }
                )

        candidate_reports.sort(
            key=lambda report: (bool(report["accepted"]), float(report["objective"])),
            reverse=True,
        )
        elites = candidate_reports[:4]
        generation_best = elites[0]
        if float(generation_best["objective"]) > float(best_candidate["objective"]):
            best_candidate = generation_best
        history.append(
            {
                "generation": generation,
                "best_candidate_id": generation_best["candidate_id"],
                "best_objective": _round(generation_best["objective"]),
                "best_detection_quality": generation_best["performance"]["detection_quality"],
                "best_context_sensitivity": generation_best["performance"]["context_sensitivity"],
                "best_macro_ece": generation_best["performance"]["macro_ece"],
            }
        )
        next_population: list[dict[str, Any]] = []
        for elite_index, elite in enumerate(elites):
            next_population.append(
                {
                    "candidate_id": f"g{generation + 1}-elite{elite_index}",
                    "generation": generation + 1,
                    "theta": deepcopy(elite["theta"]),
                    "parent_ids": [elite["candidate_id"]],
                    "mutation_type": "elite-carryover",
                }
            )
        while len(next_population) < population_size:
            parent_a = rng.choice(elites)
            parent_b = rng.choice(elites)
            child_theta = _crossover_genome(parent_a["theta"], parent_b["theta"], rng)
            next_population.append(
                {
                    "candidate_id": f"g{generation + 1}-child{len(next_population)}",
                    "generation": generation + 1,
                    "theta": child_theta,
                    "parent_ids": [parent_a["candidate_id"], parent_b["candidate_id"]],
                    "mutation_type": "crossover",
                }
            )
        population_specs = next_population

    mutation_bias_atlas = _mutation_bias_atlas(lineage_logs)
    best_thresholds = _normalize_thresholds(best_candidate["theta"]["global_thresholds"])
    return {
        "policy_version": "bseo-control-policy-v1",
        "best_candidate_id": best_candidate["candidate_id"],
        "recommended_thresholds": best_thresholds,
        "best_theta": best_candidate["theta"],
        "best_objective": _round(best_candidate["objective"]),
        "best_performance": best_candidate["performance"],
        "best_bias_signature": best_candidate["bias_signature"],
        "baseline": {
            "candidate_id": baseline_report["candidate_id"],
            "thresholds": _normalize_thresholds(root_theta["global_thresholds"]),
            "performance": baseline_report["performance"],
            "bias_signature": baseline_report["bias_signature"],
            "objective": _round(baseline_report["objective"]),
        },
        "population_size": population_size,
        "generations": generations,
        "history": history,
        "lineage_logs": lineage_logs,
        "mutation_bias_atlas": mutation_bias_atlas,
        "policy_artifact": {
            "policy_version": "bseo-control-policy-v1",
            "recommended_thresholds": best_thresholds,
            "control_genome": best_candidate["theta"],
            "bias_signature": best_candidate["bias_signature"],
            "objective": {
                "score": _round(best_candidate["objective"]),
                "detection_quality": best_candidate["performance"]["detection_quality"],
                "context_sensitivity": best_candidate["performance"]["context_sensitivity"],
                "calibration": best_candidate["performance"]["calibration"],
                "mutation_stability": _round(best_candidate["mutation_stability"]),
                "channel_lock_in": best_candidate["performance"]["channel_lock_in"],
                "genre_confusion": best_candidate["performance"]["genre_confusion"],
            },
            "mutation_bias_atlas": mutation_bias_atlas,
        },
    }
