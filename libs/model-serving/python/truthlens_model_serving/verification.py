from __future__ import annotations

from dataclasses import dataclass

from truthlens_model_serving.scorer import ModelSignals
from truthlens_shared_schemas.contracts import ScoreItemRequest


@dataclass(slots=True)
class VerificationResult:
    status: str
    triggers: list[str]
    reasons: list[str]
    summary: str | None
    review_recommended: bool


def _threshold_near(risk_score: float, thresholds: dict[str, float]) -> bool:
    for value in thresholds.values():
        if abs(risk_score - float(value)) <= 0.03:
            return True
    return False


def run_selective_verification(
    payload: ScoreItemRequest,
    signals: ModelSignals,
    *,
    thresholds: dict[str, float],
) -> VerificationResult:
    triggers: list[str] = []
    reasons: list[str] = []
    feature_summary = signals.feature_summary
    content_class = str(feature_summary.get("content_class", "unknown"))
    transcript_mismatch = float(feature_summary.get("transcript_mismatch_score", 0.0))
    guardrail = str(feature_summary.get("taxonomy_guardrail", "")) or "balanced-context"
    negative_biases = [
        str(value)
        for value in dict(feature_summary.get("bias_profile", {})).get("negative_biases", [])
        if value
    ]

    if float(signals.calibrated_score) >= float(thresholds.get("report_prompt_threshold", 0.65)) - 0.05:
        triggers.append("high-risk")
    if float(signals.uncertainty) >= 0.35:
        triggers.append("high-uncertainty")
    mismatch_threshold = 0.72 if content_class in {"music", "art", "satire", "gaming"} else 0.55
    if transcript_mismatch >= mismatch_threshold:
        triggers.append("high-mismatch")
    if _threshold_near(float(signals.calibrated_score), thresholds):
        triggers.append("threshold-near")
    if bool(payload.runtime_context.review_requested):
        triggers.append("review-flow")

    if not triggers:
        return VerificationResult(
            status="not-requested",
            triggers=[],
            reasons=[],
            summary=None,
            review_recommended=False,
        )

    if "high-mismatch" in triggers:
        reasons.append(
            "Selective verification confirmed elevated packaging mismatch after applying "
            f"the '{guardrail}' guardrail."
        )
    if "high-uncertainty" in triggers:
        reasons.append("Selective verification marked the item as uncertainty-sensitive near a review boundary.")
    if "threshold-near" in triggers:
        reasons.append("Selective verification ran because the calibrated score was close to an action threshold.")
    if "review-flow" in triggers:
        reasons.append("Selective verification was requested explicitly by a review-oriented client surface.")
    if negative_biases:
        reasons.append("Selective verification observed negative bias context: " + ", ".join(negative_biases) + ".")
    if float(signals.anomaly_score) >= 0.58:
        reasons.append("Selective verification observed an elevated packaging anomaly sidecar score.")

    summary = " ".join(reasons[:2]) if reasons else "Selective verification completed without additional findings."
    review_recommended = any(
        trigger in triggers for trigger in ("high-risk", "high-uncertainty", "high-mismatch", "review-flow")
    )

    return VerificationResult(
        status="completed",
        triggers=triggers,
        reasons=reasons,
        summary=summary,
        review_recommended=review_recommended,
    )
