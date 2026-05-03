from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import Literal
from typing import cast

from truthlens_feature_extractors import CONTENT_CLASSES
from truthlens_explanation_engine.explainer import build_explanation
from truthlens_model_serving import (
    load_feedback_events,
    load_model_info,
    predict_item_signals,
    summarize_feedback_events,
)
from truthlens_model_serving.registry import ARCHITECTURE_PLAN_VERSION, HEAD_SPEC_VERSION
from truthlens_model_serving.verification import run_selective_verification
from truthlens_shared_schemas.contracts import (
    ActionDecisionBasis,
    AdaptiveSemanticEvidenceRoute,
    ArtifactProvenance,
    BiasProfile,
    ContentClass,
    RecommendedAction,
    ScoreItemRequest,
    ScoreResult,
    VerificationProvenance,
)

DEFAULT_THRESHOLDS = {
    "badge_threshold": 0.35,
    "blur_threshold": 0.60,
    "report_prompt_threshold": 0.80,
    "hide_threshold": 0.93,
}
THRESHOLD_NAMES = tuple(DEFAULT_THRESHOLDS.keys())

DEFAULT_RUNTIME_POLICY_CONFIG: dict[str, Any] = {
    "policy_mode": "bseo-shadow",
    "bseo_min_confidence": 0.58,
    "bseo_max_uncertainty": 0.45,
    "bseo_artifact_max_age_hours": 168,
}

ACTION_NAMES = [action.value for action in RecommendedAction]
_ACTION_BY_NAME = {action.value: action for action in RecommendedAction}
_POLICY_RUNTIME_STATS: dict[str, Any] = {
    "total_decisions": 0,
    "threshold_decisions": 0,
    "bseo_live_decisions": 0,
    "bseo_shadow_evaluations": 0,
    "bseo_shadow_divergences": 0,
    "bseo_fallbacks": 0,
    "rl_live_decisions": 0,
    "rl_shadow_evaluations": 0,
    "rl_shadow_divergences": 0,
    "rl_fallbacks": 0,
    "final_action_counts": {action: 0 for action in ACTION_NAMES},
    "threshold_action_counts": {action: 0 for action in ACTION_NAMES},
    "rl_action_counts": {action: 0 for action in ACTION_NAMES},
    "fallback_reasons": Counter(),
}


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[4]


def _load_threshold_profile() -> dict[str, float]:
    path = _repo_root() / "configs" / "thresholds" / "default.json"
    if not path.exists():
        return DEFAULT_THRESHOLDS.copy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "badge_threshold": float(payload.get("badge_threshold", DEFAULT_THRESHOLDS["badge_threshold"])),
        "blur_threshold": float(payload.get("blur_threshold", DEFAULT_THRESHOLDS["blur_threshold"])),
        "report_prompt_threshold": float(
            payload.get("report_prompt_threshold", DEFAULT_THRESHOLDS["report_prompt_threshold"])
        ),
        "hide_threshold": float(payload.get("hide_threshold", DEFAULT_THRESHOLDS["hide_threshold"])),
    }


def _load_bandit_adjustments() -> dict[str, float]:
    path = _repo_root() / "configs" / "thresholds" / "contextual-bandit.json"
    if not path.exists():
        return {
            "badge_threshold_offset": 0.0,
            "blur_threshold_offset": 0.0,
            "report_prompt_threshold_offset": 0.0,
            "hide_threshold_offset": 0.0,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "badge_threshold_offset": float(payload.get("badge_threshold_offset", 0.0)),
        "blur_threshold_offset": float(payload.get("blur_threshold_offset", 0.0)),
        "report_prompt_threshold_offset": float(payload.get("report_prompt_threshold_offset", 0.0)),
        "hide_threshold_offset": float(payload.get("hide_threshold_offset", 0.0)),
    }


def _load_evolutionary_search() -> dict[str, Any] | None:
    path = _repo_root() / "configs" / "thresholds" / "evolutionary-search.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_thresholds(thresholds: dict[str, float]) -> dict[str, float]:
    badge = max(0.15, min(float(thresholds["badge_threshold"]), 0.55))
    blur = max(badge + 0.08, min(float(thresholds["blur_threshold"]), 0.82))
    report = max(blur + 0.08, min(float(thresholds["report_prompt_threshold"]), 0.94))
    hide = max(report + 0.06, min(float(thresholds["hide_threshold"]), 0.99))
    return {
        "badge_threshold": round(min(badge, 0.55), 4),
        "blur_threshold": round(min(blur, 0.82), 4),
        "report_prompt_threshold": round(min(report, 0.94), 4),
        "hide_threshold": round(min(hide, 0.99), 4),
    }


def _normalized_policy_mode(mode: str) -> str:
    if mode == "rl-shadow":
        return "bseo-shadow"
    if mode == "rl-live":
        return "bseo-live"
    return mode


def _load_runtime_policy_config() -> dict[str, Any]:
    path = _repo_root() / "configs" / "thresholds" / "runtime-policy.json"
    merged: dict[str, Any] = DEFAULT_RUNTIME_POLICY_CONFIG.copy()
    if not path.exists():
        payload: dict[str, Any] = {}
    else:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        payload = cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}
    if payload:
        merged.update({key: value for key, value in payload.items() if value is not None})
    if "bseo_min_confidence" not in merged and "rl_min_confidence" in merged:
        merged["bseo_min_confidence"] = merged["rl_min_confidence"]
    if "bseo_max_uncertainty" not in merged and "rl_max_uncertainty" in merged:
        merged["bseo_max_uncertainty"] = merged["rl_max_uncertainty"]
    if "bseo_artifact_max_age_hours" not in merged and "rl_artifact_max_age_hours" in merged:
        merged["bseo_artifact_max_age_hours"] = merged["rl_artifact_max_age_hours"]
    merged["policy_mode"] = str(merged.get("policy_mode", "bseo-shadow"))
    merged["resolved_policy_mode"] = _normalized_policy_mode(merged["policy_mode"])
    merged["bseo_min_confidence"] = float(merged.get("bseo_min_confidence", 0.58))
    merged["bseo_max_uncertainty"] = float(merged.get("bseo_max_uncertainty", 0.45))
    merged["bseo_artifact_max_age_hours"] = float(merged.get("bseo_artifact_max_age_hours", 168))
    merged["rl_min_confidence"] = merged["bseo_min_confidence"]
    merged["rl_max_uncertainty"] = merged["bseo_max_uncertainty"]
    merged["rl_artifact_max_age_hours"] = merged["bseo_artifact_max_age_hours"]
    return merged


def _load_bseo_policy_artifact() -> dict[str, Any] | None:
    path = _repo_root() / "configs" / "thresholds" / "bseo-policy.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _feedback_summary() -> dict[str, Any]:
    return summarize_feedback_events(load_feedback_events()[-200:])


def _feedback_bias(summary: dict[str, Any]) -> float:
    action_counts = summary["action_counts"]
    total_events = max(int(summary["total_events"]), 1)
    bias = (
        action_counts.get("not-misleading", 0) * 0.015
        + action_counts.get("undo-hide", 0) * 0.01
        - action_counts.get("report", 0) * 0.012
        - action_counts.get("confirm-report", 0) * 0.012
        - action_counts.get("mute-channel-local", 0) * 0.018
    ) / total_events
    return round(max(-0.08, min(0.08, bias)), 4)


def _channel_feedback_bias(channel_name: str, summary: dict[str, Any]) -> float:
    channel_key = channel_name.strip().lower()
    if not channel_key or channel_key == "unknown channel":
        return 0.0
    profile = summary["channel_profiles"].get(channel_key)
    if not profile:
        return 0.0
    return float(profile["bias"])


def _personalize_thresholds(payload: ScoreItemRequest, base_thresholds: dict[str, float]) -> dict[str, float]:
    strict_bias = -0.05 if payload.user_context.strict_mode else 0.0
    correction_bias = min(payload.user_context.prior_corrections * 0.005, 0.03)
    return {
        "badge_threshold": round(max(0.15, base_thresholds["badge_threshold"] + strict_bias + correction_bias), 3),
        "blur_threshold": round(max(0.25, base_thresholds["blur_threshold"] + strict_bias + correction_bias), 3),
        "report_prompt_threshold": round(
            max(0.45, base_thresholds["report_prompt_threshold"] + strict_bias + correction_bias),
            3,
        ),
        "hide_threshold": round(max(0.65, base_thresholds["hide_threshold"] + correction_bias), 3),
    }


def _resolve_threshold_action(
    risk_score: float,
    thresholds: dict[str, float],
    *,
    muted_channel: bool,
) -> RecommendedAction:
    if muted_channel:
        return RecommendedAction.HIDE
    if risk_score < thresholds["badge_threshold"]:
        return RecommendedAction.NONE
    if risk_score < thresholds["blur_threshold"]:
        return RecommendedAction.BADGE
    if risk_score < thresholds["report_prompt_threshold"]:
        return RecommendedAction.BLUR
    if risk_score < thresholds["hide_threshold"]:
        return RecommendedAction.ASK_REPORT
    return RecommendedAction.HIDE


def _artifact_age_hours(generated_at: str | None) -> float | None:
    if not generated_at:
        return None
    normalized = generated_at.replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - timestamp).total_seconds() / 3600.0, 3)


def _summarize_bseo_artifact(
    artifact: dict[str, Any] | None,
    runtime_config: dict[str, Any],
) -> dict[str, Any]:
    if artifact is None:
        return {
            "status": "missing",
            "available": False,
            "compatible": False,
            "stale": False,
            "policy_version": "bseo-control-policy-v1",
            "state_count": 0,
            "age_hours": None,
            "generated_at": None,
            "build_id": None,
            "reason": "bseo policy artifact is missing",
        }

    age_hours = _artifact_age_hours(str(artifact.get("generated_at", "")) or None)
    control_genome = artifact.get("control_genome", {})
    compatible = (
        isinstance(control_genome, dict)
        and str(artifact.get("head_spec_version", "")) == HEAD_SPEC_VERSION
        and str(artifact.get("architecture_plan_version", "")) == ARCHITECTURE_PLAN_VERSION
    )
    stale = bool(
        age_hours is not None
        and age_hours > float(runtime_config.get("bseo_artifact_max_age_hours", 168.0))
    )
    status = "compatible"
    reason = ""
    if not compatible:
        status = "incompatible"
        reason = "bseo policy artifact contracts do not match the current runtime"
    elif stale:
        status = "stale"
        reason = "bseo policy artifact is older than the allowed runtime age"

    return {
        "status": status,
        "available": True,
        "compatible": compatible,
        "stale": stale,
        "policy_version": str(artifact.get("policy_version", "bseo-control-policy-v1")),
        "state_count": len(control_genome),
        "age_hours": age_hours,
        "generated_at": artifact.get("generated_at"),
        "build_id": artifact.get("build_id"),
        "reason": reason or None,
    }


def _policy_version_for_mode(
    mode: str,
    artifact_summary: dict[str, Any],
) -> str:
    resolved_mode = _normalized_policy_mode(mode)
    if resolved_mode == "threshold-default":
        return "adaptive-threshold-v1"
    base = str(artifact_summary.get("policy_version", "bseo-control-policy-v1"))
    suffix = "shadow" if resolved_mode == "bseo-shadow" else "live"
    return f"{base}-{suffix}"


def _runtime_metrics_payload() -> dict[str, Any]:
    total_decisions = max(int(_POLICY_RUNTIME_STATS["total_decisions"]), 1)
    shadow_evaluations = max(int(_POLICY_RUNTIME_STATS["bseo_shadow_evaluations"]), 1)
    return {
        "total_decisions": int(_POLICY_RUNTIME_STATS["total_decisions"]),
        "threshold_decisions": int(_POLICY_RUNTIME_STATS["threshold_decisions"]),
        "bseo_live_decisions": int(_POLICY_RUNTIME_STATS["bseo_live_decisions"]),
        "bseo_shadow_evaluations": int(_POLICY_RUNTIME_STATS["bseo_shadow_evaluations"]),
        "bseo_shadow_divergences": int(_POLICY_RUNTIME_STATS["bseo_shadow_divergences"]),
        "bseo_fallbacks": int(_POLICY_RUNTIME_STATS["bseo_fallbacks"]),
        "rl_live_decisions": int(_POLICY_RUNTIME_STATS["rl_live_decisions"]),
        "rl_shadow_evaluations": int(_POLICY_RUNTIME_STATS["rl_shadow_evaluations"]),
        "rl_shadow_divergences": int(_POLICY_RUNTIME_STATS["rl_shadow_divergences"]),
        "rl_fallbacks": int(_POLICY_RUNTIME_STATS["rl_fallbacks"]),
        "fallback_rate": round(int(_POLICY_RUNTIME_STATS["bseo_fallbacks"]) / total_decisions, 4),
        "divergence_rate": round(
            int(_POLICY_RUNTIME_STATS["bseo_shadow_divergences"]) / shadow_evaluations,
            4,
        ),
        "final_action_counts": dict(_POLICY_RUNTIME_STATS["final_action_counts"]),
        "threshold_action_counts": dict(_POLICY_RUNTIME_STATS["threshold_action_counts"]),
        "bseo_action_counts": dict(_POLICY_RUNTIME_STATS["rl_action_counts"]),
        "rl_action_counts": dict(_POLICY_RUNTIME_STATS["rl_action_counts"]),
        "fallback_reasons": dict(_POLICY_RUNTIME_STATS["fallback_reasons"]),
    }


def _record_policy_metrics(
    *,
    threshold_action: RecommendedAction,
    final_action: RecommendedAction,
    bseo_action: RecommendedAction | None,
    shadow_diverged: bool,
    fallback_reason: str | None,
    used_bseo_live: bool,
) -> None:
    _POLICY_RUNTIME_STATS["total_decisions"] += 1
    _POLICY_RUNTIME_STATS["threshold_action_counts"][threshold_action.value] += 1
    _POLICY_RUNTIME_STATS["final_action_counts"][final_action.value] += 1
    if used_bseo_live:
        _POLICY_RUNTIME_STATS["bseo_live_decisions"] += 1
        _POLICY_RUNTIME_STATS["rl_live_decisions"] += 1
    else:
        _POLICY_RUNTIME_STATS["threshold_decisions"] += 1
    if bseo_action is not None:
        _POLICY_RUNTIME_STATS["bseo_shadow_evaluations"] += 1
        _POLICY_RUNTIME_STATS["rl_shadow_evaluations"] += 1
        _POLICY_RUNTIME_STATS["rl_action_counts"][bseo_action.value] += 1
    if shadow_diverged:
        _POLICY_RUNTIME_STATS["bseo_shadow_divergences"] += 1
        _POLICY_RUNTIME_STATS["rl_shadow_divergences"] += 1
    if fallback_reason:
        _POLICY_RUNTIME_STATS["bseo_fallbacks"] += 1
        _POLICY_RUNTIME_STATS["rl_fallbacks"] += 1
        _POLICY_RUNTIME_STATS["fallback_reasons"][fallback_reason] += 1


def _uncertainty_bucket(uncertainty: float) -> Literal["low", "medium", "high"]:
    if uncertainty >= 0.35:
        return "high"
    if uncertainty >= 0.2:
        return "medium"
    return "low"


def _path_scores(signals: Any) -> dict[str, float]:
    return {
        "text": round(float(signals.text_score), 4),
        "vision": round(float(signals.vision_score), 4),
        "metadata": round(float(signals.metadata_score), 4),
        "history": round(float(signals.history_score), 4),
        "anomaly": round(float(signals.anomaly_score), 4),
        "fusion": round(float(signals.fusion_score), 4),
        "calibration": round(float(signals.calibrated_score), 4),
    }


def _path_contributors(feature_summary: dict[str, Any]) -> dict[str, list[str]]:
    mapping = {
        "text": "text_top_contributors",
        "vision": "vision_top_contributors",
        "metadata": "metadata_top_contributors",
        "history": "history_top_contributors",
        "anomaly": "anomaly_top_contributors",
        "fusion": "fusion_top_contributors",
    }
    contributors: dict[str, list[str]] = {}
    for path_name, key in mapping.items():
        values = feature_summary.get(key, [])
        if not isinstance(values, list):
            contributors[path_name] = []
            continue
        contributors[path_name] = [
            str(item.get("name", "")).replace("_", " ")
            for item in values[:3]
            if isinstance(item, dict) and item.get("name")
        ]
    return contributors


def _semantic_route_payload(feature_summary: dict[str, Any]) -> dict[str, Any]:
    route = feature_summary.get("semantic_evidence_route", {})
    return route if isinstance(route, dict) else {}


def _route_requires_review_floor(route: dict[str, Any]) -> bool:
    return (
        route.get("runtime_route") == "ambiguous_escalated"
        and route.get("adversarial_guard") == "triggered"
    )


def _resolve_bseo_action(
    payload: ScoreItemRequest,
    *,
    signals: Any,
    runtime_config: dict[str, Any],
    artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    artifact_summary = _summarize_bseo_artifact(artifact, runtime_config)
    if signals.mode != "trained":
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "bootstrap-mode",
        }
    if not artifact_summary["available"]:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "missing-artifact",
        }
    if not artifact_summary["compatible"]:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "incompatible-artifact",
        }
    if artifact_summary["stale"]:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "stale-artifact",
        }
    if float(signals.confidence) < float(runtime_config["bseo_min_confidence"]):
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "low-confidence",
        }
    if float(signals.uncertainty) > float(runtime_config["bseo_max_uncertainty"]):
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "high-uncertainty",
        }
    content_class = str(signals.feature_summary.get("content_class", "unknown"))
    if content_class not in CONTENT_CLASSES:
        content_class = "unknown"
    if float(signals.feature_summary.get("content_class_confidence", 0.0)) < 0.2:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "low-class-confidence",
        }
    assert artifact is not None
    control_genome = artifact.get("control_genome", {}) if artifact is not None else {}
    if not isinstance(control_genome, dict):
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "missing-control-genome",
        }
    thresholds = _normalize_thresholds(
        {
            name: float(artifact.get("recommended_thresholds", {}).get(name, DEFAULT_THRESHOLDS[name]))
            + float(control_genome.get("content_threshold_offsets", {}).get(content_class, 0.0))
            for name in THRESHOLD_NAMES
        }
    )
    bias_metrics = signals.feature_summary.get("bias_primitives", {})
    channel_prior_dependency = float(
        bias_metrics.get(
            "channel_prior_dependency",
            min(
                1.0,
                float(payload.channel.prior_flags) * 0.12
                + float(signals.feature_summary.get("channel_risk_mean", 0.0)) * 0.4
                + float(signals.feature_summary.get("repeat_template_rate", 0.0)) * 0.2,
            ),
        )
    )
    mismatch_weight = float(control_genome.get("mismatch_weight_by_class", {}).get(content_class, 1.0))
    sensational_weight = float(
        control_genome.get("sensational_weight_by_class", {}).get(content_class, 1.0)
    )
    semantic_route = _semantic_route_payload(signals.feature_summary)
    runtime_route = str(semantic_route.get("runtime_route", "ambiguous_escalated"))
    adversarial_guard = str(semantic_route.get("adversarial_guard", "triggered"))
    mismatch_pressure = str(semantic_route.get("mismatch_pressure", "normal"))
    if mismatch_pressure == "reduced" and runtime_route == "minimal_creative" and adversarial_guard == "clean":
        mismatch_weight *= 0.55
    elif mismatch_pressure == "elevated":
        mismatch_weight = max(mismatch_weight, 1.12) * 1.08
        sensational_weight = max(sensational_weight, 1.05)
    elif adversarial_guard == "triggered" and content_class in {"music", "art"}:
        mismatch_weight = max(mismatch_weight, 1.0)
        sensational_weight = max(sensational_weight, 1.0)
    policy_score = float(signals.calibrated_score)
    policy_score += float(signals.feature_summary.get("transcript_mismatch_score", 0.0)) * 0.14 * mismatch_weight
    policy_score += min(float(signals.feature_summary.get("token_hits", 0.0)) / 4.0, 1.0) * 0.1 * sensational_weight
    policy_score += channel_prior_dependency * 0.08 * float(control_genome.get("channel_prior_temperature", 1.0))
    policy_score += float(signals.uncertainty) * 0.06 * float(control_genome.get("uncertainty_escalation_bias", 1.0))
    if (
        content_class in {"music", "art"}
        and float(signals.feature_summary.get("content_class_confidence", 0.0)) >= 0.65
        and runtime_route == "minimal_creative"
        and adversarial_guard == "clean"
    ):
        policy_score -= 0.04
    elif content_class in {"news", "commentary", "documentary", "promo", "unknown"}:
        policy_score += 0.03
    if content_class == "satire" and float(signals.feature_summary.get("content_class_confidence", 0.0)) < 0.72:
        policy_score += 0.02
    if _route_requires_review_floor(semantic_route):
        policy_score = max(policy_score, thresholds["badge_threshold"])
    policy_score = max(0.0, min(policy_score, 1.0))
    action = _resolve_threshold_action(policy_score, thresholds, muted_channel=False)
    if action not in _ACTION_BY_NAME.values():
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "fallback_reason": "invalid-action",
        }
    return {
        "eligible": True,
        "artifact_summary": artifact_summary,
        "action": action,
        "thresholds": thresholds,
        "policy_score": round(policy_score, 4),
        "content_class": content_class,
        "fallback_reason": None,
    }


def get_policy_profile() -> dict[str, Any]:
    thresholds = _load_threshold_profile()
    bandit_adjustments = _load_bandit_adjustments()
    summary = _feedback_summary()
    bias = _feedback_bias(summary)
    adjusted = {
        name: round(value + bias, 3) if name != "hide_threshold" else round(value + max(bias, 0.0), 3)
        for name, value in thresholds.items()
    }
    adjusted["badge_threshold"] = round(adjusted["badge_threshold"] + bandit_adjustments["badge_threshold_offset"], 3)
    adjusted["blur_threshold"] = round(adjusted["blur_threshold"] + bandit_adjustments["blur_threshold_offset"], 3)
    adjusted["report_prompt_threshold"] = round(
        adjusted["report_prompt_threshold"] + bandit_adjustments["report_prompt_threshold_offset"],
        3,
    )
    adjusted["hide_threshold"] = round(adjusted["hide_threshold"] + bandit_adjustments["hide_threshold_offset"], 3)
    evolutionary_search = _load_evolutionary_search()
    runtime_config = _load_runtime_policy_config()
    artifact_summary = _summarize_bseo_artifact(_load_bseo_policy_artifact(), runtime_config)
    return {
        "policy_version": _policy_version_for_mode(str(runtime_config["policy_mode"]), artifact_summary),
        "policy_mode": runtime_config["policy_mode"],
        "resolved_policy_mode": runtime_config["resolved_policy_mode"],
        "base_thresholds": thresholds,
        "bandit_adjustments": bandit_adjustments,
        "evolutionary_search": evolutionary_search,
        "feedback_bias": round(bias, 3),
        "effective_thresholds": adjusted,
        "runtime_policy_config": runtime_config,
        "bseo_artifact": artifact_summary,
        "rl_artifact": artifact_summary,
        "runtime_metrics": _runtime_metrics_payload(),
        "feedback_summary": {
            "total_events": summary["total_events"],
            "correction_rate": summary["correction_rate"],
            "top_channels": summary["top_channels"],
        },
    }


def score_item(payload: ScoreItemRequest) -> ScoreResult:
    signals = predict_item_signals(payload)
    policy_profile = get_policy_profile()
    thresholds = _personalize_thresholds(payload, policy_profile["effective_thresholds"])
    feedback_summary = _feedback_summary()
    channel_bias = _channel_feedback_bias(
        payload.channel.channel_name,
        feedback_summary,
    )
    thresholds = {
        "badge_threshold": round(max(0.12, thresholds["badge_threshold"] + channel_bias), 3),
        "blur_threshold": round(max(0.2, thresholds["blur_threshold"] + channel_bias), 3),
        "report_prompt_threshold": round(
            max(0.38, thresholds["report_prompt_threshold"] + channel_bias),
            3,
        ),
        "hide_threshold": round(max(0.55, thresholds["hide_threshold"] + min(channel_bias, 0.0)), 3),
    }
    risk_score = signals.calibrated_score
    confidence = signals.confidence
    uncertainty = signals.uncertainty
    muted_channels = {channel.strip().lower() for channel in payload.user_context.muted_channels}
    muted_channel_key = payload.channel.channel_name.strip().lower()
    muted_channel = bool(muted_channel_key) and muted_channel_key != "unknown channel" and muted_channel_key in muted_channels
    semantic_route = _semantic_route_payload(signals.feature_summary)
    if not muted_channel and _route_requires_review_floor(semantic_route):
        route_floor = float(thresholds["badge_threshold"])
        if float(risk_score) < route_floor:
            risk_score = route_floor
            signals.feature_summary["semantic_route_risk_floor"] = round(route_floor, 4)
            signals.feature_summary["runtime_policy_note"] = (
                "Adaptive semantic routing escalated this ambiguous creative-looking item for review "
                "instead of treating creative keywords as sufficient for a green route."
            )
    verification = run_selective_verification(payload, signals, thresholds=thresholds)
    signals.feature_summary["verification"] = {
        "status": verification.status,
        "triggers": list(verification.triggers),
        "reasons": list(verification.reasons),
        "summary": verification.summary,
        "review_recommended": verification.review_recommended,
    }

    threshold_action = _resolve_threshold_action(risk_score, thresholds, muted_channel=muted_channel)
    final_action = threshold_action
    bseo_action: RecommendedAction | None = None
    shadow_diverged = False
    fallback_reason: str | None = None
    used_bseo_live = False
    active_thresholds = thresholds

    runtime_config = policy_profile["runtime_policy_config"]
    policy_mode = str(runtime_config["resolved_policy_mode"])
    if not muted_channel and policy_mode in {"bseo-shadow", "bseo-live"}:
        bseo_decision = _resolve_bseo_action(
            payload,
            signals=signals,
            runtime_config=runtime_config,
            artifact=_load_bseo_policy_artifact(),
        )
        bseo_action = bseo_decision.get("action")
        fallback_reason = bseo_decision.get("fallback_reason")
        if bseo_action is not None and bseo_action != threshold_action:
            shadow_diverged = True
        if policy_mode == "bseo-live" and bseo_decision["eligible"] and bseo_action is not None:
            final_action = bseo_action
            used_bseo_live = True
            active_thresholds = bseo_decision.get("thresholds", thresholds)
            risk_score = float(bseo_decision.get("policy_score", risk_score))
            signals.feature_summary["policy_adjusted_risk"] = risk_score
            if final_action != threshold_action:
                signals.feature_summary["runtime_policy_note"] = (
                    "Runtime BSEO policy selected "
                    f"'{final_action.value}' for content class '{bseo_decision.get('content_class', 'unknown')}' "
                    f"instead of the threshold-policy action '{threshold_action.value}'."
                )
        elif bseo_action is not None:
            signals.feature_summary["policy_adjusted_risk"] = float(bseo_decision.get("policy_score", risk_score))

    explanation = build_explanation(payload, signals, active_thresholds, final_action)
    if final_action == RecommendedAction.HIDE and muted_channel:
        explanation.reasons.append("This channel is locally muted, so TruthLens hid it immediately.")
    _record_policy_metrics(
        threshold_action=threshold_action,
        final_action=final_action,
        bseo_action=bseo_action,
        shadow_diverged=shadow_diverged,
        fallback_reason=fallback_reason,
        used_bseo_live=used_bseo_live,
    )
    bias_profile = signals.feature_summary.get("bias_profile", {})
    model_info = load_model_info()
    artifact_summary = policy_profile["bseo_artifact"]
    if muted_channel:
        decisive_layer = "muted-channel"
    elif used_bseo_live:
        decisive_layer = "bseo-live"
    else:
        decisive_layer = "threshold"
    policy_reason = signals.feature_summary.get("runtime_policy_note")
    if not isinstance(policy_reason, str) or not policy_reason:
        policy_reason = verification.summary if verification.status == "completed" else None

    resolved_verification_status = cast(
        Literal["not-requested", "completed", "failed-soft"],
        verification.status,
    )
    resolved_verification_triggers = cast(
        list[Literal["high-risk", "high-uncertainty", "high-mismatch", "threshold-near", "review-flow"]],
        list(verification.triggers),
    )
    resolved_decisive_layer = cast(
        Literal["threshold", "bseo-live", "muted-channel"],
        decisive_layer,
    )
    resolved_content_class = cast(
        ContentClass,
        str(signals.feature_summary.get("content_class", "unknown")),
    )

    return ScoreResult(
        risk_score=round(risk_score, 2),
        fused_score=round(float(signals.fusion_score), 2),
        calibrated_score=round(float(signals.calibrated_score), 2),
        confidence=round(confidence, 2),
        uncertainty=round(uncertainty, 2),
        uncertainty_bucket=_uncertainty_bucket(float(uncertainty)),
        path_scores=_path_scores(signals),
        path_contributors=_path_contributors(signals.feature_summary),
        content_class=resolved_content_class,
        content_class_confidence=round(
            float(signals.feature_summary.get("content_class_confidence", 0.0)),
            2,
        ),
        semantic_evidence_route=AdaptiveSemanticEvidenceRoute.model_validate(semantic_route),
        bias_profile=BiasProfile(
            metrics=dict(bias_profile.get("metrics", {})) if isinstance(bias_profile, dict) else {},
            positive_biases=list(bias_profile.get("positive_biases", []))
            if isinstance(bias_profile, dict)
            else [],
            negative_biases=list(bias_profile.get("negative_biases", []))
            if isinstance(bias_profile, dict)
            else [],
            guardrail_applied=bias_profile.get("guardrail_applied")
            if isinstance(bias_profile, dict)
            else None,
        ),
        verification=VerificationProvenance(
            status=resolved_verification_status,
            triggers=resolved_verification_triggers,
            reasons=list(verification.reasons),
            summary=verification.summary,
            review_recommended=verification.review_recommended,
        ),
        action_decision_basis=ActionDecisionBasis(
            threshold_action=threshold_action,
            final_action=final_action,
            decisive_layer=resolved_decisive_layer,
            verification_considered=verification.status == "completed",
            policy_reason=policy_reason,
        ),
        policy_mode=str(policy_profile["policy_mode"]),
        resolved_policy_mode=str(policy_profile["resolved_policy_mode"]),
        artifact_provenance=ArtifactProvenance(
            model_version=str(model_info.get("model_version", signals.model_version)),
            model_build_id=model_info.get("build_id"),
            policy_version=str(policy_profile["policy_version"]),
            policy_build_id=artifact_summary.get("build_id"),
            policy_artifact_status=artifact_summary.get("status"),
        ),
        recommended_action=final_action,
        reasons=explanation.reasons,
        explanation_id=explanation.explanation_id,
        explanation_summary=explanation.summary,
        evidence=explanation.evidence,
    )
