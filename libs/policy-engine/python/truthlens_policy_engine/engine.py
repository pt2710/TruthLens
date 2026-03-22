from __future__ import annotations

from truthlens_explanation_engine.explainer import build_reasons
from truthlens_shared_schemas.contracts import RecommendedAction, ScoreItemRequest, ScoreResult

SENSATIONAL_TOKENS = {
    "breaking",
    "shocking",
    "confirmed",
    "aliens",
    "secret",
    "exposed",
    "you won't believe",
    "urgent",
    "what they don't want",
}


def score_item(payload: ScoreItemRequest) -> ScoreResult:
    title = payload.title.lower()
    token_hits = sum(1 for token in SENSATIONAL_TOKENS if token in title)
    risk_score = min(0.15 + token_hits * 0.17 + payload.channel.prior_flags * 0.03, 0.98)
    confidence = min(0.55 + token_hits * 0.1, 0.95)
    uncertainty = max(0.05, round(1.0 - confidence, 2))

    if risk_score < 0.35:
        action = RecommendedAction.NONE
    elif risk_score < 0.60:
        action = RecommendedAction.BADGE
    elif risk_score < 0.80:
        action = RecommendedAction.BLUR
    else:
        action = RecommendedAction.ASK_REPORT

    reasons = build_reasons(payload, token_hits, action)

    return ScoreResult(
        risk_score=round(risk_score, 2),
        confidence=round(confidence, 2),
        uncertainty=round(uncertainty, 2),
        recommended_action=action,
        reasons=reasons,
    )
