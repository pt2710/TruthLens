from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecommendedAction(str, Enum):
    NONE = "none"
    BADGE = "badge"
    BLUR = "blur"
    HIDE = "hide"
    ASK_REPORT = "ask-report"


class ChannelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_name: str = Field(min_length=1)
    channel_url: str | None = None
    prior_flags: int = 0
    channel_history_features: dict[str, float] = Field(default_factory=dict)


class ItemMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_time: str | None = None
    duration_seconds: int | None = None
    view_count: int | None = None
    like_count: int | None = None


class UserContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict_mode: bool = False
    muted_channels: list[str] = Field(default_factory=list)
    prior_corrections: int = Field(default=0, ge=0)


class ScoreItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    thumbnail_ref: str | None = None
    transcript_excerpt: str | None = None
    metadata: ItemMetadata = Field(default_factory=ItemMetadata)
    channel: ChannelInfo
    user_context: UserContext = Field(default_factory=UserContext)


class ExplanationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "title",
        "thumbnail",
        "history",
        "transcript",
        "metadata",
        "policy",
        "user-context",
        "uncertainty",
    ]
    label: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    details: str | None = None


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    recommended_action: RecommendedAction = RecommendedAction.NONE
    reasons: list[str] = Field(default_factory=list)
    explanation_id: str | None = None
    explanation_summary: str | None = None
    evidence: list[ExplanationEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_reason_for_actions(self) -> "ScoreResult":
        if self.recommended_action != RecommendedAction.NONE and not self.reasons:
            msg = "Active recommendations require at least one reason."
            raise ValueError(msg)
        if self.recommended_action != RecommendedAction.NONE and not self.explanation_id:
            msg = "Active recommendations require an explanation_id."
            raise ValueError(msg)
        if self.recommended_action != RecommendedAction.NONE and not self.explanation_summary:
            msg = "Active recommendations require an explanation_summary."
            raise ValueError(msg)
        return self


class BatchScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScoreItemRequest] = Field(min_length=1)


class BatchScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: dict[str, ScoreResult]


class FeedbackEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    item_hash: str | None = None
    channel_name: str | None = None
    model_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    action_shown: RecommendedAction
    user_action: str = Field(min_length=1)
    explanation_id: str | None = None
    before_score: float | None = Field(default=None, ge=0.0, le=1.0)
    after_score: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: str = Field(min_length=1)


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    platform: str
    source_run_id: str
    source_url: str
    collected_at: str
    title: str
    channel_name: str
    thumbnail_path: str
    description: str
    tags: list[str]
    hashtags: list[str]
    transcript_excerpt: str | None = None
    metadata: dict[str, Any]
    history: dict[str, Any]
    features: dict[str, Any]
    labels: dict[str, Any]
    provenance: dict[str, Any]
    annotator_notes: list[str]
