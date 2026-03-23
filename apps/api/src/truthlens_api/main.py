from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from truthlens_api.settings import settings
from truthlens_model_serving import (
    append_feedback_event,
    append_score_event,
    describe_model,
    summarize_feedback_events,
)
from truthlens_policy_engine import get_policy_profile, score_item
from truthlens_shared_schemas.contracts import (
    BatchScoreRequest,
    BatchScoreResponse,
    FeedbackEvent,
    ScoreItemRequest,
    ScoreResult,
)

app = FastAPI(title="TruthLens API", version="0.1.0")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_score_event(
    payload: ScoreItemRequest,
    result: ScoreResult,
    *,
    model_version: str,
    policy_version: str,
) -> None:
    append_score_event(
        {
            "item_id": payload.item_id,
            "channel_name": payload.channel.channel_name,
            "model_version": model_version,
            "policy_version": policy_version,
            "recommended_action": result.recommended_action.value,
            "risk_score": result.risk_score,
            "confidence": result.confidence,
            "uncertainty": result.uncertainty,
            "explanation_id": result.explanation_id,
            "timestamp": _utc_timestamp(),
        }
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}


@app.get("/model-info")
def model_info() -> dict[str, object]:
    return describe_model()


@app.get("/policy-info")
def policy_info() -> dict[str, object]:
    return get_policy_profile()


@app.post("/score-item", response_model=ScoreResult)
def score_single_item(payload: ScoreItemRequest) -> ScoreResult:
    result = score_item(payload)
    model_version = str(describe_model().get("model_version", "bootstrap-v0"))
    policy_version = str(get_policy_profile().get("policy_version", "adaptive-threshold-v1"))
    _audit_score_event(
        payload,
        result,
        model_version=model_version,
        policy_version=policy_version,
    )
    return result


@app.post("/batch-score", response_model=BatchScoreResponse)
def batch_score(payload: BatchScoreRequest) -> BatchScoreResponse:
    model_version = str(describe_model().get("model_version", "bootstrap-v0"))
    policy_version = str(get_policy_profile().get("policy_version", "adaptive-threshold-v1"))
    results: dict[str, ScoreResult] = {}
    for item in payload.items:
        result = score_item(item)
        results[item.item_id] = result
        _audit_score_event(
            item,
            result,
            model_version=model_version,
            policy_version=policy_version,
        )
    return BatchScoreResponse(results=results)


@app.post("/feedback")
def feedback(payload: FeedbackEvent) -> dict[str, str]:
    append_feedback_event(payload.model_dump())
    return {"status": "accepted", "feedback_log_path": settings.feedback_log_path}


@app.get("/feedback-summary")
def feedback_summary() -> dict[str, object]:
    return summarize_feedback_events()
