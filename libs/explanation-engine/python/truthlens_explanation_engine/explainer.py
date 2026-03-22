from __future__ import annotations

from truthlens_shared_schemas.contracts import RecommendedAction, ScoreItemRequest


def build_reasons(
    payload: ScoreItemRequest,
    sensational_token_hits: int,
    action: RecommendedAction,
) -> list[str]:
    reasons: list[str] = []
    if sensational_token_hits:
        reasons.append("Title contains strong sensational framing patterns.")
    if payload.channel.prior_flags > 0:
        reasons.append("Channel history contributes supporting risk context.")
    if action == RecommendedAction.ASK_REPORT:
        reasons.append("Risk score crossed the high-risk prompt threshold.")
    return reasons
