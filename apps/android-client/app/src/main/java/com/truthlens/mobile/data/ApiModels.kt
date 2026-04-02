package com.truthlens.mobile.data

import com.google.gson.annotations.SerializedName

data class UserContextDto(
    @SerializedName("strict_mode") val strictMode: Boolean = false,
    @SerializedName("muted_channels") val mutedChannels: List<String> = emptyList(),
    @SerializedName("prior_corrections") val priorCorrections: Int = 0,
)

data class ItemMetadataDto(
    @SerializedName("upload_time") val uploadTime: String? = null,
    @SerializedName("duration_seconds") val durationSeconds: Int? = null,
    @SerializedName("view_count") val viewCount: Int? = null,
    @SerializedName("like_count") val likeCount: Int? = null,
)

data class ExplanationEvidenceDto(
    val kind: String,
    val label: String,
    val score: Double? = null,
    val details: String? = null,
)

data class ScoreResultDto(
    @SerializedName("risk_score") val riskScore: Double,
    val confidence: Double,
    val uncertainty: Double,
    @SerializedName("recommended_action") val recommendedAction: String,
    val reasons: List<String>,
    @SerializedName("explanation_id") val explanationId: String?,
    @SerializedName("explanation_summary") val explanationSummary: String?,
    val evidence: List<ExplanationEvidenceDto>,
)

data class ReviewPromptStateDto(
    @SerializedName("workflow_mode") val workflowMode: String,
    val label: String,
    val reason: String,
    @SerializedName("auto_open") val autoOpen: Boolean,
)

data class ReviewStatusEventDto(
    val phase: String,
    val label: String,
    val status: String,
    val details: String? = null,
)

data class ManualReportSuggestionIssueDto(
    @SerializedName("issue_type") val issueType: String,
    val suggested: Boolean,
    val comment: String,
)

data class ManualReportSuggestionResponseDto(
    val issues: List<ManualReportSuggestionIssueDto>,
    @SerializedName("suggested_outcome") val suggestedOutcome: String,
    @SerializedName("suggestion_model") val suggestionModel: String,
)

data class ExplanationBundleDto(
    @SerializedName("explanation_id") val explanationId: String?,
    @SerializedName("explanation_summary") val explanationSummary: String?,
    val reasons: List<String>,
    val evidence: List<ExplanationEvidenceDto>,
)

data class YouTubeAuthStatusDto(
    val configured: Boolean,
    val connected: Boolean,
    @SerializedName("auth_url") val authUrl: String?,
    @SerializedName("channel_name") val channelName: String?,
)

data class MobileResolvedWatchContextDto(
    @SerializedName("target_url") val targetUrl: String,
    @SerializedName("video_id") val videoId: String,
    val title: String,
    @SerializedName("thumbnail_ref") val thumbnailRef: String?,
    @SerializedName("channel_name") val channelName: String,
    @SerializedName("channel_url") val channelUrl: String?,
    @SerializedName("description_snapshot") val descriptionSnapshot: String?,
    @SerializedName("transcript_excerpt") val transcriptExcerpt: String?,
    @SerializedName("transcript_available") val transcriptAvailable: Boolean,
    @SerializedName("channel_context") val channelContext: String?,
    @SerializedName("music_likelihood") val musicLikelihood: Double,
    val metadata: ItemMetadataDto,
)

data class MobileAnalyzeShareRequestDto(
    @SerializedName("target_url") val targetUrl: String,
    @SerializedName("user_context") val userContext: UserContextDto = UserContextDto(),
)

data class MobileAnalyzeShareResponseDto(
    @SerializedName("model_version") val modelVersion: String,
    @SerializedName("policy_version") val policyVersion: String,
    @SerializedName("watch_context") val watchContext: MobileResolvedWatchContextDto,
    val score: ScoreResultDto,
    val explanation: ExplanationBundleDto,
    @SerializedName("review_prompt") val reviewPrompt: ReviewPromptStateDto?,
    @SerializedName("draft_suggestion") val draftSuggestion: ManualReportSuggestionResponseDto,
    @SerializedName("youtube_auth") val youTubeAuth: YouTubeAuthStatusDto,
    @SerializedName("status_stream") val statusStream: List<ReviewStatusEventDto>,
)

data class ManualReportIssueDto(
    @SerializedName("issue_type") val issueType: String,
    val comment: String,
    @SerializedName("original_comment") val originalComment: String? = null,
)

data class ManualReportOptimizationRequestDto(
    @SerializedName("workflow_mode") val workflowMode: String,
    @SerializedName("target_url") val targetUrl: String?,
    @SerializedName("title_snapshot") val titleSnapshot: String,
    @SerializedName("channel_name") val channelName: String,
    @SerializedName("transcript_excerpt") val transcriptExcerpt: String?,
    @SerializedName("requested_outcome") val requestedOutcome: String,
    val issues: List<ManualReportIssueDto>,
)

data class ManualReportOptimizationResponseDto(
    val issues: List<ManualReportIssueDto>,
    @SerializedName("optimization_model") val optimizationModel: String,
    @SerializedName("report_text") val reportText: String,
)

data class ManualReportDto(
    @SerializedName("workflow_mode") val workflowMode: String,
    @SerializedName("target_url") val targetUrl: String?,
    @SerializedName("thumbnail_ref") val thumbnailRef: String?,
    @SerializedName("title_snapshot") val titleSnapshot: String,
    @SerializedName("transcript_excerpt") val transcriptExcerpt: String?,
    val issues: List<ManualReportIssueDto>,
    @SerializedName("requested_outcome") val requestedOutcome: String,
    @SerializedName("optimize_requested") val optimizeRequested: Boolean,
    @SerializedName("optimize_applied") val optimizeApplied: Boolean,
    @SerializedName("optimization_model") val optimizationModel: String?,
    @SerializedName("report_text") val reportText: String,
)

data class FeedbackEventDto(
    @SerializedName("item_id") val itemId: String,
    @SerializedName("item_hash") val itemHash: String? = null,
    @SerializedName("channel_name") val channelName: String?,
    @SerializedName("model_version") val modelVersion: String,
    @SerializedName("policy_version") val policyVersion: String,
    @SerializedName("action_shown") val actionShown: String,
    @SerializedName("user_action") val userAction: String,
    @SerializedName("explanation_id") val explanationId: String? = null,
    @SerializedName("before_score") val beforeScore: Double? = null,
    @SerializedName("after_score") val afterScore: Double? = null,
    val timestamp: String,
    @SerializedName("manual_report") val manualReport: ManualReportDto? = null,
)

data class YouTubeReportRequestDto(
    @SerializedName("target_url") val targetUrl: String,
    @SerializedName("report_text") val reportText: String,
    @SerializedName("issue_types") val issueTypes: List<String>,
)

data class YouTubeReportResponseDto(
    val status: String,
    @SerializedName("reason_id") val reasonId: String,
    @SerializedName("reason_label") val reasonLabel: String,
    @SerializedName("secondary_reason_id") val secondaryReasonId: String?,
    @SerializedName("secondary_reason_label") val secondaryReasonLabel: String?,
)

data class AppSettings(
    val apiBaseUrl: String = "http://10.0.2.2:8000/",
    val apiKey: String = "",
    val autoOptimizeDrafts: Boolean = true,
    val showDebugInfo: Boolean = false,
)

data class RecentAnalysisEntry(
    val targetUrl: String,
    val title: String,
    val score: Double,
    val recommendedAction: String,
    val summary: String,
    val timestampIso: String,
)
