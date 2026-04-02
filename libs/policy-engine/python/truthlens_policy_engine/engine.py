from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from truthlens_evaluation import state_key_for_score
from truthlens_explanation_engine.explainer import build_explanation
from truthlens_model_serving import load_feedback_events, predict_item_signals, summarize_feedback_events
from truthlens_model_serving.registry import ARCHITECTURE_PLAN_VERSION, HEAD_SPEC_VERSION
from truthlens_shared_schemas.contracts import RecommendedAction, ScoreItemRequest, ScoreResult

DEFAULT_THRESHOLDS = {
    "badge_threshold": 0.35,
    "blur_threshold": 0.60,
    "report_prompt_threshold": 0.80,
    "hide_threshold": 0.93,
}

DEFAULT_RUNTIME_POLICY_CONFIG = {
    "policy_mode": "threshold-default",
    "rl_min_confidence": 0.72,
    "rl_max_uncertainty": 0.35,
    "rl_artifact_max_age_hours": 168,
}

ACTION_NAMES = [action.value for action in RecommendedAction]
_ACTION_BY_NAME = {action.value: action for action in RecommendedAction}
_POLICY_RUNTIME_STATS = {
    "total_decisions": 0,
    "threshold_decisions": 0,
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


def _load_runtime_policy_config() -> dict[str, Any]:
    path = _repo_root() / "configs" / "thresholds" / "runtime-policy.json"
    if not path.exists():
        return DEFAULT_RUNTIME_POLICY_CONFIG.copy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    merged = DEFAULT_RUNTIME_POLICY_CONFIG.copy()
    if isinstance(payload, dict):
        merged.update({key: value for key, value in payload.items() if value is not None})
    merged["policy_mode"] = str(merged.get("policy_mode", "threshold-default"))
    merged["rl_min_confidence"] = float(merged.get("rl_min_confidence", 0.72))
    merged["rl_max_uncertainty"] = float(merged.get("rl_max_uncertainty", 0.35))
    merged["rl_artifact_max_age_hours"] = float(merged.get("rl_artifact_max_age_hours", 168))
    return merged


def _load_rl_policy_artifact() -> dict[str, Any] | None:
    path = _repo_root() / "configs" / "thresholds" / "rl-policy.json"
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


def _summarize_rl_artifact(
    artifact: dict[str, Any] | None,
    runtime_config: dict[str, Any],
) -> dict[str, Any]:
    if artifact is None:
        return {
            "status": "missing",
            "available": False,
            "compatible": False,
            "stale": False,
            "policy_version": "rl-action-policy-v1",
            "state_count": 0,
            "age_hours": None,
            "generated_at": None,
            "build_id": None,
            "reason": "rl policy artifact is missing",
        }

    age_hours = _artifact_age_hours(str(artifact.get("generated_at", "")) or None)
    state_count = len(artifact.get("policy", {})) if isinstance(artifact.get("policy"), dict) else 0
    compatible = (
        isinstance(artifact.get("policy"), dict)
        and str(artifact.get("head_spec_version", "")) == HEAD_SPEC_VERSION
        and str(artifact.get("architecture_plan_version", "")) == ARCHITECTURE_PLAN_VERSION
    )
    stale = bool(
        age_hours is not None and age_hours > float(runtime_config.get("rl_artifact_max_age_hours", 168.0))
    )
    status = "compatible"
    reason = ""
    if not compatible:
        status = "incompatible"
        reason = "rl policy artifact contracts do not match the current runtime"
    elif stale:
        status = "stale"
        reason = "rl policy artifact is older than the allowed runtime age"

    return {
        "status": status,
        "available": True,
        "compatible": compatible,
        "stale": stale,
        "policy_version": str(artifact.get("policy_version", "rl-action-policy-v1")),
        "state_count": state_count,
        "age_hours": age_hours,
        "generated_at": artifact.get("generated_at"),
        "build_id": artifact.get("build_id"),
        "reason": reason or None,
    }


def _policy_version_for_mode(
    mode: str,
    artifact_summary: dict[str, Any],
) -> str:
    if mode == "threshold-default":
        return "adaptive-threshold-v1"
    base = str(artifact_summary.get("policy_version", "rl-action-policy-v1"))
    suffix = "shadow" if mode == "rl-shadow" else "live"
    return f"{base}-{suffix}"


def _runtime_metrics_payload() -> dict[str, Any]:
    total_decisions = max(int(_POLICY_RUNTIME_STATS["total_decisions"]), 1)
    shadow_evaluations = max(int(_POLICY_RUNTIME_STATS["rl_shadow_evaluations"]), 1)
    return {
        "total_decisions": int(_POLICY_RUNTIME_STATS["total_decisions"]),
        "threshold_decisions": int(_POLICY_RUNTIME_STATS["threshold_decisions"]),
        "rl_live_decisions": int(_POLICY_RUNTIME_STATS["rl_live_decisions"]),
        "rl_shadow_evaluations": int(_POLICY_RUNTIME_STATS["rl_shadow_evaluations"]),
        "rl_shadow_divergences": int(_POLICY_RUNTIME_STATS["rl_shadow_divergences"]),
        "rl_fallbacks": int(_POLICY_RUNTIME_STATS["rl_fallbacks"]),
        "fallback_rate": round(int(_POLICY_RUNTIME_STATS["rl_fallbacks"]) / total_decisions, 4),
        "divergence_rate": round(
            int(_POLICY_RUNTIME_STATS["rl_shadow_divergences"]) / shadow_evaluations,
            4,
        ),
        "final_action_counts": dict(_POLICY_RUNTIME_STATS["final_action_counts"]),
        "threshold_action_counts": dict(_POLICY_RUNTIME_STATS["threshold_action_counts"]),
        "rl_action_counts": dict(_POLICY_RUNTIME_STATS["rl_action_counts"]),
        "fallback_reasons": dict(_POLICY_RUNTIME_STATS["fallback_reasons"]),
    }


def _record_policy_metrics(
    *,
    threshold_action: RecommendedAction,
    final_action: RecommendedAction,
    rl_action: RecommendedAction | None,
    shadow_diverged: bool,
    fallback_reason: str | None,
    used_rl_live: bool,
) -> None:
    _POLICY_RUNTIME_STATS["total_decisions"] += 1
    _POLICY_RUNTIME_STATS["threshold_action_counts"][threshold_action.value] += 1
    _POLICY_RUNTIME_STATS["final_action_counts"][final_action.value] += 1
    if used_rl_live:
        _POLICY_RUNTIME_STATS["rl_live_decisions"] += 1
    else:
        _POLICY_RUNTIME_STATS["threshold_decisions"] += 1
    if rl_action is not None:
        _POLICY_RUNTIME_STATS["rl_shadow_evaluations"] += 1
        _POLICY_RUNTIME_STATS["rl_action_counts"][rl_action.value] += 1
    if shadow_diverged:
        _POLICY_RUNTIME_STATS["rl_shadow_divergences"] += 1
    if fallback_reason:
        _POLICY_RUNTIME_STATS["rl_fallbacks"] += 1
        _POLICY_RUNTIME_STATS["fallback_reasons"][fallback_reason] += 1


def _resolve_rl_action(
    payload: ScoreItemRequest,
    *,
    signals: Any,
    runtime_config: dict[str, Any],
    artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    artifact_summary = _summarize_rl_artifact(artifact, runtime_config)
    state_key = state_key_for_score(signals.calibrated_score, signals.uncertainty)

    if signals.mode != "trained":
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "bootstrap-mode",
        }
    if not artifact_summary["available"]:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "missing-artifact",
        }
    if not artifact_summary["compatible"]:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "incompatible-artifact",
        }
    if artifact_summary["stale"]:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "stale-artifact",
        }
    if float(signals.confidence) < float(runtime_config["rl_min_confidence"]):
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "low-confidence",
        }
    if float(signals.uncertainty) > float(runtime_config["rl_max_uncertainty"]):
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "high-uncertainty",
        }
    channel_name = payload.channel.channel_name.strip().lower()
    if not channel_name or channel_name == "unknown channel":
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "missing-channel-context",
        }
    policy_map = artifact.get("policy", {}) if artifact is not None else {}
    if not isinstance(policy_map, dict) or state_key not in policy_map:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "missing-state",
        }
    action_name = str(policy_map[state_key])
    action = _ACTION_BY_NAME.get(action_name)
    if action is None:
        return {
            "eligible": False,
            "artifact_summary": artifact_summary,
            "state_key": state_key,
            "fallback_reason": "invalid-action",
        }
    return {
        "eligible": True,
        "artifact_summary": artifact_summary,
        "state_key": state_key,
        "action": action,
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
    artifact_summary = _summarize_rl_artifact(_load_rl_policy_artifact(), runtime_config)
    return {
        "policy_version": _policy_version_for_mode(str(runtime_config["policy_mode"]), artifact_summary),
        "policy_mode": runtime_config["policy_mode"],
        "base_thresholds": thresholds,
        "bandit_adjustments": bandit_adjustments,
        "evolutionary_search": evolutionary_search,
        "feedback_bias": round(bias, 3),
        "effective_thresholds": adjusted,
        "runtime_policy_config": runtime_config,
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

    threshold_action = _resolve_threshold_action(risk_score, thresholds, muted_channel=muted_channel)
    final_action = threshold_action
    rl_action: RecommendedAction | None = None
    shadow_diverged = False
    fallback_reason: str | None = None
    used_rl_live = False

    runtime_config = policy_profile["runtime_policy_config"]
    policy_mode = str(runtime_config["policy_mode"])
    if not muted_channel and policy_mode in {"rl-shadow", "rl-live"}:
        rl_decision = _resolve_rl_action(
            payload,
            signals=signals,
            runtime_config=runtime_config,
            artifact=_load_rl_policy_artifact(),
        )
        rl_action = rl_decision.get("action")
        fallback_reason = rl_decision.get("fallback_reason")
        if rl_action is not None and rl_action != threshold_action:
            shadow_diverged = True
        if policy_mode == "rl-live" and rl_decision["eligible"] and rl_action is not None:
            final_action = rl_action
            used_rl_live = True
            if final_action != threshold_action:
                signals.feature_summary["runtime_policy_note"] = (
                    f"Runtime RL policy selected '{final_action.value}' for state "
                    f"{rl_decision['state_key']} instead of the threshold-policy action "
                    f"'{threshold_action.value}'."
                )

    explanation = build_explanation(payload, signals, thresholds, final_action)
    if final_action == RecommendedAction.HIDE and muted_channel:
        explanation.reasons.append("This channel is locally muted, so TruthLens hid it immediately.")
    _record_policy_metrics(
        threshold_action=threshold_action,
        final_action=final_action,
        rl_action=rl_action,
        shadow_diverged=shadow_diverged,
        fallback_reason=fallback_reason,
        used_rl_live=used_rl_live,
    )

    return ScoreResult(
        risk_score=round(risk_score, 2),
        confidence=round(confidence, 2),
        uncertainty=round(uncertainty, 2),
        recommended_action=final_action,
        reasons=explanation.reasons,
        explanation_id=explanation.explanation_id,
        explanation_summary=explanation.summary,
        evidence=explanation.evidence,
    )
