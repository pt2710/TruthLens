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


class RuntimeContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surface: Literal[
        "extension-feed",
        "extension-watch",
        "mobile-share",
        "api",
        "trainer",
        "unknown",
    ] = "unknown"
    review_requested: bool = False
    source_provenance: str | None = None


class ObservationDistilledFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_index: int | None = Field(default=None, ge=0)
    link_kind: Literal["watch", "shorts", "other", "unknown"] = "unknown"
    has_thumbnail: bool = False
    has_description_snapshot: bool = False
    has_transcript_excerpt: bool = False
    title_token_count: int = Field(default=0, ge=0)
    description_token_count: int = Field(default=0, ge=0)
    channel_known: bool = True
    duration_seconds: int | None = Field(default=None, ge=0)


class ObservationScoreSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    calibrated_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    recommended_action: RecommendedAction = RecommendedAction.NONE
    content_class: ContentClass = ContentClass.UNKNOWN
    content_class_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation_id: str | None = None


class ObservationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: str = Field(min_length=1)
    collector: Literal["extension-dom", "api", "unknown"] = "unknown"
    collector_version: str | None = None
    session_id: str | None = None
    page_url: str | None = None
    source_path: str | None = None


class BrowserObservationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    item_hash: str | None = None
    title_snapshot: str = Field(min_length=1)
    channel_name: str | None = None
    channel_url: str | None = None
    link_url: str | None = None
    thumbnail_ref: str | None = None
    description_snapshot: str | None = None
    transcript_excerpt: str | None = None
    metadata: ItemMetadata = Field(default_factory=ItemMetadata)
    runtime_context: RuntimeContext = Field(default_factory=RuntimeContext)
    distilled_features: ObservationDistilledFeatures = Field(default_factory=ObservationDistilledFeatures)
    score_snapshot: ObservationScoreSnapshot = Field(default_factory=ObservationScoreSnapshot)
    provenance: ObservationProvenance


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
    runtime_context: RuntimeContext = Field(default_factory=RuntimeContext)


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
        "verification",
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


VerificationStatus = Literal["not-requested", "completed", "failed-soft"]
VerificationTrigger = Literal[
    "high-risk",
    "high-uncertainty",
    "high-mismatch",
    "threshold-near",
    "review-flow",
]


class VerificationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus = "not-requested"
    triggers: list[VerificationTrigger] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    summary: str | None = None
    review_recommended: bool = False


class ActionDecisionBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_action: RecommendedAction = RecommendedAction.NONE
    final_action: RecommendedAction = RecommendedAction.NONE
    decisive_layer: Literal["threshold", "bseo-live", "muted-channel"] = "threshold"
    verification_considered: bool = False
    policy_reason: str | None = None


class ArtifactProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version: str | None = None
    model_build_id: str | None = None
    policy_version: str | None = None
    policy_build_id: str | None = None
    policy_artifact_status: str | None = None


class LabelCandidateFeedbackSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_events: int = Field(default=0, ge=0)
    risk_event_count: int = Field(default=0, ge=0)
    benign_event_count: int = Field(default=0, ge=0)
    manual_report_count: int = Field(default=0, ge=0)
    last_user_action: str | None = None


class LabelCandidateSplitSafety(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_membership: Literal[
        "existing-batch",
        "supplemental-intake",
        "supplemental-adjudicated",
    ] = "supplemental-intake"
    split_status: Literal[
        "assigned",
        "blocked-until-ingestion",
        "excluded-from-training",
    ] = "blocked-until-ingestion"
    split_name: Literal["train", "validation", "test", "unknown"] = "unknown"
    dataset_build_id: str | None = None
    annotation_run_id: str | None = None
    eligible_for_training: bool = False
    leakage_guard_reason: str | None = None


class LabelCandidateProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str = Field(min_length=1)
    generator: str = "browser-feedback-intake-v1"
    candidate_sources: list[
        Literal["pipeline-batch", "browser-observation", "feedback-event", "manual-report"]
    ] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    feedback_event_ids: list[str] = Field(default_factory=list)
    source_paths: list[str] = Field(default_factory=list)


LabelCandidateQueue = Literal["review", "hard-negative", "disagreement"]


class LabelCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    queue_name: LabelCandidateQueue
    origin: Literal["pipeline-batch", "supplemental-intake"] = "pipeline-batch"
    title: str = Field(min_length=1)
    channel_name: str | None = None
    weak_label_score: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty_bucket: str | None = None
    source_trust_flag: str | None = None
    template_cluster: str | None = None
    prior_flags: int | None = Field(default=None, ge=0)
    content_class: str = Field(default="unknown", min_length=1)
    content_class_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    dominant_bias_risk: str | None = None
    bias_review_required: bool | None = None
    current_labels: dict[str, bool] = Field(default_factory=dict)
    annotator_notes: list[str] = Field(default_factory=list)
    queue_reason: str | None = None
    distilled_features: ObservationDistilledFeatures | None = None
    feedback_summary: LabelCandidateFeedbackSummary = Field(default_factory=LabelCandidateFeedbackSummary)
    provenance: LabelCandidateProvenance
    split_safety: LabelCandidateSplitSafety = Field(default_factory=LabelCandidateSplitSafety)


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
    fused_score: float = Field(default=0.0, ge=0.0, le=1.0)
    calibrated_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    uncertainty_bucket: Literal["low", "medium", "high"] = "low"
    path_scores: dict[str, float] = Field(default_factory=dict)
    path_contributors: dict[str, list[str]] = Field(default_factory=dict)
    content_class: ContentClass = ContentClass.UNKNOWN
    content_class_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bias_profile: BiasProfile = Field(default_factory=BiasProfile)
    verification: VerificationProvenance = Field(default_factory=VerificationProvenance)
    action_decision_basis: ActionDecisionBasis = Field(default_factory=ActionDecisionBasis)
    policy_mode: str = "threshold-default"
    resolved_policy_mode: str = "threshold-default"
    artifact_provenance: ArtifactProvenance = Field(default_factory=ArtifactProvenance)
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

    feedback_id: str | None = None
    item_id: str = Field(min_length=1)
    item_hash: str | None = None
    observation_id: str | None = None
    channel_name: str | None = None
    model_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    action_shown: RecommendedAction
    user_action: str = Field(min_length=1)
    explanation_id: str | None = None
    before_score: float | None = Field(default=None, ge=0.0, le=1.0)
    after_score: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: str = Field(min_length=1)
    runtime_context: RuntimeContext | None = None
    artifact_provenance: ArtifactProvenance | None = None
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
