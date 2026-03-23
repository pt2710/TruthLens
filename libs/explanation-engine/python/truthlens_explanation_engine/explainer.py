from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Literal

from truthlens_model_serving.scorer import ModelSignals
from truthlens_shared_schemas.contracts import ExplanationEvidence, RecommendedAction, ScoreItemRequest


@dataclass(slots=True)
class ExplanationBundle:
    explanation_id: str
    summary: str
    reasons: list[str]
    evidence: list[ExplanationEvidence]


def _append_evidence(
    evidence: list[ExplanationEvidence],
    kind: Literal[
        "title",
        "thumbnail",
        "history",
        "transcript",
        "metadata",
        "policy",
        "user-context",
        "uncertainty",
    ],
    label: str,
    *,
    score: float | None = None,
    details: str | None = None,
) -> None:
    evidence.append(
        ExplanationEvidence(
            kind=kind,
            label=label,
            score=round(score, 2) if score is not None else None,
            details=details,
        )
    )


def build_explanation(
    payload: ScoreItemRequest,
    signals: ModelSignals,
    thresholds: dict[str, float],
    action: RecommendedAction,
) -> ExplanationBundle:
    reasons: list[str] = []
    evidence: list[ExplanationEvidence] = []
    muted_channels = {channel.strip().lower() for channel in payload.user_context.muted_channels}
    if muted_channels and payload.channel.channel_name.strip().lower() in muted_channels:
        reason = "Channel is locally muted in the current user profile."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "user-context",
            "Channel muted locally",
            score=1.0,
            details=reason,
        )
    if signals.text_score >= max(signals.vision_score, signals.metadata_score):
        reason = "Title contains strong sensational framing patterns."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "title",
            "Sensational title framing",
            score=signals.text_score,
            details=reason,
        )
    if signals.vision_score > 0.55:
        reason = "Thumbnail-style features match exaggerated shock composition."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "thumbnail",
            "Thumbnail exaggeration pattern",
            score=signals.vision_score,
            details=reason,
        )
    if payload.channel.prior_flags > 0 and max(signals.metadata_score, signals.history_score) > 0.42:
        reason = "Channel history contributes supporting risk context."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "history",
            "Channel history raises supporting risk context",
            score=max(signals.metadata_score, signals.history_score),
            details=reason,
        )
    if signals.feature_summary.get("repeat_template_rate", 0.0) > 0.45:
        reason = "Channel is repeating a high-risk template pattern unusually often."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "history",
            "Repeated high-risk template pattern",
            score=signals.feature_summary.get("repeat_template_rate", 0.0),
            details=reason,
        )
    if signals.feature_summary.get("thumbnail_text_density", 0.0) > 0.4:
        reason = "Thumbnail appears text-heavy for a standard feed card."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "thumbnail",
            "Thumbnail text density is elevated",
            score=signals.feature_summary.get("thumbnail_text_density", 0.0),
            details=reason,
        )
    if signals.feature_summary.get("transcript_mismatch_score", 0.0) > 0.55:
        reason = "Title and transcript excerpt diverge in a way that suggests framing mismatch."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "transcript",
            "Title and transcript mismatch",
            score=signals.feature_summary.get("transcript_mismatch_score", 0.0),
            details=reason,
        )
    if signals.uncertainty >= 0.35:
        reason = "Model uncertainty is elevated, so manual review is safer."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "uncertainty",
            "Uncertainty is elevated",
            score=signals.uncertainty,
            details=reason,
        )
    if action == RecommendedAction.ASK_REPORT:
        reason = f"Risk score crossed the report-prompt threshold at {thresholds['report_prompt_threshold']:.2f}."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "policy",
            "Policy crossed the report threshold",
            score=signals.calibrated_score,
            details=reason,
        )
    if action == RecommendedAction.HIDE:
        reason = "Risk and confidence crossed the local hide threshold for feed filtering."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "policy",
            "Policy crossed the local hide threshold",
            score=signals.calibrated_score,
            details=reason,
        )

    summary_parts = reasons[:2] if reasons else ["No active intervention is recommended for this item."]
    summary = " ".join(summary_parts)
    explanation_seed = "|".join(
        [
            payload.item_id,
            payload.channel.channel_name,
            action.value,
            signals.model_version,
            ",".join(reason[:24] for reason in reasons[:3]),
        ]
    )
    explanation_id = f"exp-{sha1(explanation_seed.encode('utf-8')).hexdigest()[:12]}"
    return ExplanationBundle(
        explanation_id=explanation_id,
        summary=summary,
        reasons=reasons,
        evidence=evidence,
    )


def build_reasons(
    payload: ScoreItemRequest,
    signals: ModelSignals,
    thresholds: dict[str, float],
    action: RecommendedAction,
) -> list[str]:
    return build_explanation(payload, signals, thresholds, action).reasons
