from __future__ import annotations

from truthlens_model_serving.scorer import ModelSignals
from truthlens_shared_schemas.contracts import RecommendedAction, ScoreItemRequest


def build_reasons(
    payload: ScoreItemRequest,
    signals: ModelSignals,
    thresholds: dict[str, float],
    action: RecommendedAction,
) -> list[str]:
    reasons: list[str] = []
    muted_channels = {channel.strip().lower() for channel in payload.user_context.muted_channels}
    if muted_channels and payload.channel.channel_name.strip().lower() in muted_channels:
        reasons.append("Channel is locally muted in the current user profile.")
    if signals.text_score >= max(signals.vision_score, signals.metadata_score):
        reasons.append("Title contains strong sensational framing patterns.")
    if signals.vision_score > 0.55:
        reasons.append("Thumbnail-style features match exaggerated shock composition.")
    if payload.channel.prior_flags > 0 and max(signals.metadata_score, signals.history_score) > 0.42:
        reasons.append("Channel history contributes supporting risk context.")
    if signals.feature_summary.get("repeat_template_rate", 0.0) > 0.45:
        reasons.append("Channel is repeating a high-risk template pattern unusually often.")
    if signals.feature_summary.get("thumbnail_text_density", 0.0) > 0.4:
        reasons.append("Thumbnail appears text-heavy for a standard feed card.")
    if signals.feature_summary.get("transcript_mismatch_score", 0.0) > 0.55:
        reasons.append("Title and transcript excerpt diverge in a way that suggests framing mismatch.")
    if signals.uncertainty >= 0.35:
        reasons.append("Model uncertainty is elevated, so manual review is safer.")
    if action == RecommendedAction.ASK_REPORT:
        reasons.append(
            f"Risk score crossed the report-prompt threshold at {thresholds['report_prompt_threshold']:.2f}."
        )
    if action == RecommendedAction.HIDE:
        reasons.append("Risk and confidence crossed the local hide threshold for feed filtering.")
    return reasons
