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


class ContentClass(str, Enum):
    NEWS = "news"
    COMMENTARY = "commentary"
    DOCUMENTARY = "documentary"
    MUSIC = "music"
    ART = "art"
    SATIRE = "satire"
    GAMING = "gaming"
    PROMO = "promo"
    UNKNOWN = "unknown"


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
    description_snapshot: str | None = None
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
        "taxonomy",
        "bias",
        "user-context",
        "uncertainty",
    ]
    label: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    details: str | None = None


class BiasProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: dict[str, float] = Field(default_factory=dict)
    positive_biases: list[str] = Field(default_factory=list)
    negative_biases: list[str] = Field(default_factory=list)
    guardrail_applied: str | None = None


class ManualReportIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: Literal[
        "thumbnail",
        "title",
        "description",
        "transcript",
        "channel",
        "other",
    ]
    comment: str = Field(min_length=1)
    original_comment: str | None = None


class ManualReportRequestedOutcome(str, Enum):
    MODERATE = "moderate"
    REMOVE = "remove"


class ManualReportWorkflowMode(str, Enum):
    REPORT = "report"
    VERIFY_TRANSPARENT = "verify-transparent"


class ManualReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_mode: ManualReportWorkflowMode = ManualReportWorkflowMode.REPORT
    target_url: str | None = None
    thumbnail_ref: str | None = None
    title_snapshot: str = Field(min_length=1)
    transcript_excerpt: str | None = None
    issues: list[ManualReportIssue] = Field(min_length=1)
    requested_outcome: ManualReportRequestedOutcome = ManualReportRequestedOutcome.MODERATE
    optimize_requested: bool = False
    optimize_applied: bool = False
    optimization_model: str | None = None
    report_text: str = Field(min_length=1)


class ManualReportOptimizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_mode: ManualReportWorkflowMode = ManualReportWorkflowMode.REPORT
    target_url: str | None = None
    title_snapshot: str = Field(min_length=1)
    channel_name: str = Field(min_length=1)
    transcript_excerpt: str | None = None
    requested_outcome: ManualReportRequestedOutcome = ManualReportRequestedOutcome.MODERATE
    issues: list[ManualReportIssue] = Field(min_length=1)


class ManualReportOptimizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ManualReportIssue] = Field(min_length=1)
    optimization_model: str = Field(min_length=1)
    report_text: str = Field(min_length=1)


class ManualReportSuggestionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: Literal[
        "thumbnail",
        "title",
        "description",
        "transcript",
        "channel",
        "other",
    ]
    suggested: bool
    comment: str = ""


class ManualReportSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_mode: ManualReportWorkflowMode = ManualReportWorkflowMode.REPORT
    target_url: str | None = None
    thumbnail_ref: str | None = None
    title_snapshot: str = Field(min_length=1)
    channel_name: str = Field(min_length=1)
    channel_url: str | None = None
    channel_context: str | None = None
    description_snapshot: str | None = None
    transcript_excerpt: str | None = None
    transcript_available: bool | None = None
    explanation_summary: str | None = None
    reasons: list[str] = Field(default_factory=list)
    content_class: ContentClass = ContentClass.UNKNOWN
    content_class_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bias_profile: BiasProfile = Field(default_factory=BiasProfile)


class ManualReportSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ManualReportSuggestionIssue] = Field(min_length=6, max_length=6)
    suggested_outcome: ManualReportRequestedOutcome
    suggestion_model: str = Field(min_length=1)


class ReviewPromptState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_mode: ManualReportWorkflowMode
    label: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    auto_open: bool = False


ReviewPhase = Literal[
    "resolve-share",
    "fetch-watch-metadata",
    "score-item",
    "draft-review",
    "youtube-auth",
]


class ReviewStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: ReviewPhase
    label: str = Field(min_length=1)
    status: Literal["completed"]
    details: str | None = None


class ExplanationBundlePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation_id: str | None = None
    explanation_summary: str | None = None
    reasons: list[str] = Field(default_factory=list)
    evidence: list[ExplanationEvidence] = Field(default_factory=list)


class MobileResolvedWatchContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_url: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    thumbnail_ref: str | None = None
    channel_name: str = Field(min_length=1)
    channel_url: str | None = None
    description_snapshot: str | None = None
    transcript_excerpt: str | None = None
    transcript_available: bool = False
    channel_context: str | None = None
    music_likelihood: float = Field(default=0.0, ge=0.0, le=1.0)
    content_class: ContentClass = ContentClass.UNKNOWN
    content_class_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: ItemMetadata = Field(default_factory=ItemMetadata)


class MobileAnalyzeShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_url: str = Field(min_length=1)
    user_context: UserContext = Field(default_factory=UserContext)


class MobileAnalyzeShareResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    watch_context: MobileResolvedWatchContext
    score: ScoreResult
    explanation: ExplanationBundlePayload
    review_prompt: ReviewPromptState | None = None
    draft_suggestion: ManualReportSuggestionResponse
    youtube_auth: YouTubeAuthStatus
    status_stream: list[ReviewStatusEvent] = Field(default_factory=list)


class YouTubeAuthStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    connected: bool
    auth_url: str | None = None
    channel_name: str | None = None


class YouTubeReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_url: str = Field(min_length=1)
    report_text: str = Field(min_length=1)
    issue_types: list[
        Literal[
            "thumbnail",
            "title",
            "description",
            "transcript",
            "channel",
            "other",
        ]
    ] = Field(min_length=1)


class YouTubeReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["reported"]
    reason_id: str = Field(min_length=1)
    reason_label: str = Field(min_length=1)
    secondary_reason_id: str | None = None
    secondary_reason_label: str | None = None


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    content_class: ContentClass = ContentClass.UNKNOWN
    content_class_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bias_profile: BiasProfile = Field(default_factory=BiasProfile)
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
    manual_report: ManualReport | None = None


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
