from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from truthlens_explanation_engine.explainer import build_explanation
from truthlens_model_serving import load_feedback_events, predict_item_signals, summarize_feedback_events
from truthlens_shared_schemas.contracts import RecommendedAction, ScoreItemRequest, ScoreResult

DEFAULT_THRESHOLDS = {
    "badge_threshold": 0.35,
    "blur_threshold": 0.60,
    "report_prompt_threshold": 0.80,
    "hide_threshold": 0.93,
}


def _repo_root() -> Path:
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
    if not channel_key:
        return 0.0
    profile = summary["channel_profiles"].get(channel_key)
    if not profile:
        return 0.0
    return float(profile["bias"])


def get_policy_profile() -> dict[str, Any]:
    thresholds = _load_threshold_profile()
    summary = _feedback_summary()
    bias = _feedback_bias(summary)
    adjusted = {
        name: round(value + bias, 3) if name != "hide_threshold" else round(value + max(bias, 0.0), 3)
        for name, value in thresholds.items()
    }
    return {
        "policy_version": "adaptive-threshold-v1",
        "base_thresholds": thresholds,
        "feedback_bias": round(bias, 3),
        "effective_thresholds": adjusted,
        "feedback_summary": {
            "total_events": summary["total_events"],
            "correction_rate": summary["correction_rate"],
            "top_channels": summary["top_channels"],
        },
    }


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


def score_item(payload: ScoreItemRequest) -> ScoreResult:
    signals = predict_item_signals(payload)
    policy_profile = get_policy_profile()
    thresholds = _personalize_thresholds(payload, policy_profile["effective_thresholds"])
    channel_bias = _channel_feedback_bias(
        payload.channel.channel_name,
        _feedback_summary(),
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
    muted_channel = payload.channel.channel_name.strip().lower() in muted_channels

    if muted_channel:
        action = RecommendedAction.HIDE
    elif risk_score < thresholds["badge_threshold"]:
        action = RecommendedAction.NONE
    elif risk_score < thresholds["blur_threshold"]:
        action = RecommendedAction.BADGE
    elif risk_score < thresholds["report_prompt_threshold"]:
        action = RecommendedAction.BLUR
    elif risk_score < thresholds["hide_threshold"]:
        action = RecommendedAction.ASK_REPORT
    else:
        action = RecommendedAction.HIDE

    explanation = build_explanation(payload, signals, thresholds, action)

    return ScoreResult(
        risk_score=round(risk_score, 2),
        confidence=round(confidence, 2),
        uncertainty=round(uncertainty, 2),
        recommended_action=action,
        reasons=explanation.reasons,
        explanation_id=explanation.explanation_id,
        explanation_summary=explanation.summary,
        evidence=explanation.evidence,
    )
