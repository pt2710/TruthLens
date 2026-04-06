from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any
from typing import Literal

from truthlens_model_serving.scorer import ModelSignals
from truthlens_shared_schemas.contracts import ExplanationEvidence, RecommendedAction, ScoreItemRequest


@dataclass(slots=True)
class ExplanationBundle:
    explanation_id: str
    summary: str
    reasons: list[str]
    evidence: list[ExplanationEvidence]


def _format_feature_name(name: str) -> str:
    return name.replace("_", " ")


def _contributor_details(summary: dict[str, Any], key: str, *, prefix: str) -> str | None:
    contributors = summary.get(key, [])
    if not isinstance(contributors, list) or not contributors:
        return None
    labels: list[str] = []
    for contributor in contributors[:3]:
        if not isinstance(contributor, dict):
            continue
        name = contributor.get("name")
        contribution = contributor.get("contribution")
        if not isinstance(name, str):
            continue
        if isinstance(contribution, (float, int)):
            labels.append(f"{_format_feature_name(name)} ({float(contribution):.2f})")
        else:
            labels.append(_format_feature_name(name))
    if not labels:
        return None
    return f"{prefix}: {', '.join(labels)}."


def _append_evidence(
    evidence: list[ExplanationEvidence],
    kind: Literal[
        "title",
        "thumbnail",
        "history",
        "transcript",
        "metadata",
        "policy",
        "taxonomy",
        "bias",
        "verification",
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


def _counterfactual_details(summary: dict[str, Any]) -> str | None:
    counterfactuals = summary.get("fusion_counterfactuals", [])
    if not isinstance(counterfactuals, list) or not counterfactuals:
        return None
    top = counterfactuals[0]
    if not isinstance(top, dict):
        return None
    name = top.get("name")
    score_drop = top.get("score_drop")
    if not isinstance(name, str) or not isinstance(score_drop, (float, int)):
        return None
    return f"If {_format_feature_name(name)} were removed, fusion risk drops by {float(score_drop):.2f}."


def build_explanation(
    payload: ScoreItemRequest,
    signals: ModelSignals,
    thresholds: dict[str, float],
    action: RecommendedAction,
) -> ExplanationBundle:
    reasons: list[str] = []
    evidence: list[ExplanationEvidence] = []
    music_likelihood = float(signals.feature_summary.get("music_likelihood", 0.0))
    content_class = str(signals.feature_summary.get("content_class", "unknown"))
    content_class_confidence = float(signals.feature_summary.get("content_class_confidence", 0.0))
    bias_profile = signals.feature_summary.get("bias_profile", {})
    guardrail = (
        str(bias_profile.get("guardrail_applied"))
        if isinstance(bias_profile, dict) and bias_profile.get("guardrail_applied")
        else str(signals.feature_summary.get("taxonomy_guardrail", ""))
    )
    if content_class != "unknown":
        _append_evidence(
            evidence,
            "taxonomy",
            f"Content class detected: {content_class}",
            score=content_class_confidence,
            details=(
                f"TruthLens inferred the item as '{content_class}' with confidence {content_class_confidence:.2f}."
            ),
        )
    if guardrail:
        _append_evidence(
            evidence,
            "taxonomy",
            "Class-conditioned guardrail applied",
            score=content_class_confidence if content_class != "unknown" else None,
            details=(
                f"Guardrail '{guardrail}' adjusted how cross-modal mismatch was interpreted for this class."
            ),
        )
    if isinstance(bias_profile, dict):
        positive_biases = [str(value) for value in bias_profile.get("positive_biases", []) if value]
        negative_biases = [str(value) for value in bias_profile.get("negative_biases", []) if value]
        if positive_biases:
            _append_evidence(
                evidence,
                "bias",
                "Preserved positive bias signal",
                score=min(max(content_class_confidence, 0.0), 1.0),
                details="Positive bias preserved: " + ", ".join(positive_biases) + ".",
            )
        if negative_biases:
            reasons.append("Negative bias signals required stronger intervention.")
            _append_evidence(
                evidence,
                "bias",
                "Negative bias signal triggered intervention",
                score=min(max(float(signals.calibrated_score), 0.0), 1.0),
                details="Negative bias triggered: " + ", ".join(negative_biases) + ".",
            )
    parameter_frames = signals.feature_summary.get("bseo_parameter_frames", [])
    if isinstance(parameter_frames, list) and parameter_frames:
        _append_evidence(
            evidence,
            "bias",
            "BSEO parameter frame activated",
            score=min(max(content_class_confidence, 0.0), 1.0) if content_class != "unknown" else None,
            details="Interpretation frame: " + ", ".join(str(frame) for frame in parameter_frames[:6]) + ".",
        )
    verification = signals.feature_summary.get("verification", {})
    if isinstance(verification, dict) and str(verification.get("status", "")) == "completed":
        verification_summary = str(verification.get("summary") or "").strip() or "Selective verification completed."
        verification_triggers = [
            str(value)
            for value in verification.get("triggers", [])
            if value
        ]
        _append_evidence(
            evidence,
            "verification",
            "Selective deep verification completed",
            score=min(max(float(signals.calibrated_score), 0.0), 1.0),
            details=(
                verification_summary
                + (
                    " Triggers: " + ", ".join(verification_triggers) + "."
                    if verification_triggers
                    else ""
                )
            ),
        )
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
    if music_likelihood >= 0.55:
        _append_evidence(
            evidence,
            "taxonomy",
            "Likely music-content context detected",
            score=music_likelihood,
            details="This item appears likely to be music content, so literal thumbnail-to-lyrics matching is weighted less heavily.",
        )
    if signals.text_score >= max(signals.vision_score, signals.metadata_score):
        reason = "Title contains strong sensational framing patterns."
        reasons.append(reason)
        details = _contributor_details(
            signals.feature_summary,
            "text_top_contributors",
            prefix="Top text contributors",
        )
        _append_evidence(
            evidence,
            "title",
            "Sensational title framing",
            score=signals.text_score,
            details=details or reason,
        )
    if signals.vision_score > 0.55:
        reason = "Thumbnail-style features match exaggerated shock composition."
        reasons.append(reason)
        details = _contributor_details(
            signals.feature_summary,
            "vision_top_contributors",
            prefix="Top thumbnail contributors",
        )
        if details is None:
            vision_note = signals.feature_summary.get("vision_embedding_note")
            if isinstance(vision_note, str):
                details = vision_note
        _append_evidence(
            evidence,
            "thumbnail",
            "Thumbnail exaggeration pattern",
            score=signals.vision_score,
            details=details or reason,
        )
    if signals.anomaly_score > 0.58:
        reason = "Combined thumbnail and metadata packaging looks statistically atypical relative to lower-risk training examples."
        reasons.append(reason)
        details = _contributor_details(
            signals.feature_summary,
            "anomaly_top_contributors",
            prefix="Top anomaly contributors",
        )
        _append_evidence(
            evidence,
            "metadata",
            "Packaging anomaly score is elevated",
            score=signals.anomaly_score,
            details=details or reason,
        )
    if signals.metadata_score >= max(signals.text_score, signals.vision_score, signals.history_score):
        reason = "Structured metadata features contribute strongly to the current risk estimate."
        reasons.append(reason)
        details = _contributor_details(
            signals.feature_summary,
            "metadata_top_contributors",
            prefix="Top metadata contributors",
        )
        _append_evidence(
            evidence,
            "metadata",
            "Metadata head is contributing strongly",
            score=signals.metadata_score,
            details=details or reason,
        )
    if payload.channel.prior_flags > 0 and max(signals.metadata_score, signals.history_score) > 0.42:
        reason = "Channel history contributes supporting risk context."
        reasons.append(reason)
        details = _contributor_details(
            signals.feature_summary,
            "history_top_contributors",
            prefix="Top history contributors",
        )
        if details is None:
            history_note = signals.feature_summary.get("history_sequence_note")
            if isinstance(history_note, str):
                details = history_note
        _append_evidence(
            evidence,
            "history",
            "Channel history raises supporting risk context",
            score=max(signals.metadata_score, signals.history_score),
            details=details or reason,
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
    if music_likelihood < 0.55 and signals.feature_summary.get("thumbnail_text_density", 0.0) > 0.4:
        reason = "Thumbnail appears text-heavy for a standard feed card."
        reasons.append(reason)
        _append_evidence(
            evidence,
            "thumbnail",
            "Thumbnail text density is elevated",
            score=signals.feature_summary.get("thumbnail_text_density", 0.0),
            details=reason,
        )
    transcript_threshold = 0.72 if content_class in {"music", "art", "satire", "gaming"} else 0.55
    if signals.feature_summary.get("transcript_mismatch_score", 0.0) > transcript_threshold:
        reason = (
            "Available lyrics or spoken context still diverge from the packaging even after accounting for likely music-video framing."
            if content_class in {"music", "art"}
            else "Title and transcript excerpt diverge in a way that suggests framing mismatch."
        )
        reasons.append(reason)
        _append_evidence(
            evidence,
            "transcript",
            "Packaging diverges from transcript context",
            score=signals.feature_summary.get("transcript_mismatch_score", 0.0),
            details=(
                f"{reason} Guardrail: {guardrail}."
                if guardrail
                else reason
            ),
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
    counterfactual = _counterfactual_details(signals.feature_summary)
    if counterfactual:
        _append_evidence(
            evidence,
            "policy",
            "Largest counterfactual driver",
            score=signals.calibrated_score,
            details=counterfactual,
        )
    runtime_policy_note = signals.feature_summary.get("runtime_policy_note")
    if isinstance(runtime_policy_note, str) and runtime_policy_note:
        reasons.append(runtime_policy_note)
        _append_evidence(
            evidence,
            "policy",
            "Runtime BSEO policy override",
            score=signals.calibrated_score,
            details=runtime_policy_note,
        )
    if action == RecommendedAction.ASK_REPORT:
        reason = (
            runtime_policy_note
            if isinstance(runtime_policy_note, str) and runtime_policy_note
            else f"Risk score crossed the report-prompt threshold at {thresholds['report_prompt_threshold']:.2f}."
        )
        reasons.append(reason)
        details = _contributor_details(
            signals.feature_summary,
            "fusion_top_contributors",
            prefix="Top fusion contributors",
        )
        _append_evidence(
            evidence,
            "policy",
            "Runtime BSEO policy requested manual report"
            if isinstance(runtime_policy_note, str) and runtime_policy_note
            else "Policy crossed the report threshold",
            score=signals.calibrated_score,
            details=counterfactual or details or reason,
        )
    if action == RecommendedAction.HIDE:
        reason = (
            runtime_policy_note
            if isinstance(runtime_policy_note, str) and runtime_policy_note
            else "Risk and confidence crossed the local hide threshold for feed filtering."
        )
        reasons.append(reason)
        details = _contributor_details(
            signals.feature_summary,
            "fusion_top_contributors",
            prefix="Top fusion contributors",
        )
        _append_evidence(
            evidence,
            "policy",
            "Runtime BSEO policy selected local hide"
            if isinstance(runtime_policy_note, str) and runtime_policy_note
            else "Policy crossed the local hide threshold",
            score=signals.calibrated_score,
            details=counterfactual or details or reason,
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
