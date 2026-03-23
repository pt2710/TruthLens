from __future__ import annotations

from fastapi import FastAPI

from truthlens_api.settings import settings
from truthlens_model_serving import append_feedback_event, describe_model
from truthlens_policy_engine import get_policy_profile, score_item
from truthlens_shared_schemas.contracts import (
    BatchScoreRequest,
    BatchScoreResponse,
    FeedbackEvent,
    ScoreItemRequest,
    ScoreResult,
)

app = FastAPI(title="TruthLens API", version="0.1.0")


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
    return score_item(payload)


@app.post("/batch-score", response_model=BatchScoreResponse)
def batch_score(payload: BatchScoreRequest) -> BatchScoreResponse:
    return BatchScoreResponse(results={item.item_id: score_item(item) for item in payload.items})


@app.post("/feedback")
def feedback(payload: FeedbackEvent) -> dict[str, str]:
    append_feedback_event(payload.model_dump())
    return {"status": "accepted", "feedback_log_path": settings.feedback_log_path}
