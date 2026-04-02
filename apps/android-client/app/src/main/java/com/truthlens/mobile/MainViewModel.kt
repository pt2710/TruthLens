package com.truthlens.mobile

import android.app.Application
import android.util.Patterns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.truthlens.mobile.data.AppSettings
import com.truthlens.mobile.data.FeedbackEventDto
import com.truthlens.mobile.data.ManualReportDto
import com.truthlens.mobile.data.ManualReportIssueDto
import com.truthlens.mobile.data.ManualReportOptimizationRequestDto
import com.truthlens.mobile.data.MobileAnalyzeShareRequestDto
import com.truthlens.mobile.data.MobileAnalyzeShareResponseDto
import com.truthlens.mobile.data.RecentAnalysisEntry
import com.truthlens.mobile.data.SettingsStore
import com.truthlens.mobile.data.TruthLensRepository
import com.truthlens.mobile.data.UserContextDto
import com.truthlens.mobile.data.YouTubeReportRequestDto
import java.time.OffsetDateTime
import java.time.ZoneOffset
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EditableIssue(
    val issueType: String,
    val label: String,
    val enabled: Boolean,
    val comment: String,
)

data class MainUiState(
    val currentUrl: String = "",
    val settings: AppSettings = AppSettings(),
    val analysis: MobileAnalyzeShareResponseDto? = null,
    val workflowMode: String = "report",
    val requestedOutcome: String = "moderate",
    val editableIssues: List<EditableIssue> = emptyList(),
    val optimizedReportText: String = "",
    val optimizationModel: String? = null,
    val recentAnalyses: List<RecentAnalysisEntry> = emptyList(),
    val loading: Boolean = false,
    val submitting: Boolean = false,
    val statusLines: List<String> = emptyList(),
    val errorMessage: String? = null,
    val successMessage: String? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val settingsStore = SettingsStore(application.applicationContext)
    private val repository = TruthLensRepository()
    private val _uiState = MutableStateFlow(MainUiState())
    val uiState: StateFlow<MainUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            settingsStore.settingsFlow.collect { settings ->
                _uiState.update { state -> state.copy(settings = settings) }
            }
        }
        viewModelScope.launch {
            settingsStore.recentAnalysesFlow.collect { recents ->
                _uiState.update { state -> state.copy(recentAnalyses = recents) }
            }
        }
    }

    fun ingestSharedText(text: String?) {
        if (text.isNullOrBlank()) {
            return
        }
        val trimmed = text.trim()
        _uiState.update { state -> state.copy(currentUrl = trimmed) }
        val lowered = trimmed.lowercase()
        val looksLikeYouTube = "youtube.com" in lowered || "youtu.be" in lowered
        if (Patterns.WEB_URL.matcher(trimmed).matches() && looksLikeYouTube) {
            analyzeCurrentUrl()
        }
    }

    fun updateCurrentUrl(value: String) {
        _uiState.update { state -> state.copy(currentUrl = value, errorMessage = null, successMessage = null) }
    }

    fun updateApiBaseUrl(value: String) {
        _uiState.update { state -> state.copy(settings = state.settings.copy(apiBaseUrl = value)) }
    }

    fun updateApiKey(value: String) {
        _uiState.update { state -> state.copy(settings = state.settings.copy(apiKey = value)) }
    }

    fun toggleAutoOptimize(enabled: Boolean) {
        _uiState.update { state -> state.copy(settings = state.settings.copy(autoOptimizeDrafts = enabled)) }
    }

    fun toggleShowDebug(enabled: Boolean) {
        _uiState.update { state -> state.copy(settings = state.settings.copy(showDebugInfo = enabled)) }
    }

    fun saveSettings() {
        viewModelScope.launch {
            settingsStore.saveSettings(_uiState.value.settings)
            _uiState.update { state -> state.copy(successMessage = "Settings saved.") }
        }
    }

    fun setWorkflowMode(workflowMode: String) {
        _uiState.update { state ->
            state.copy(
                workflowMode = workflowMode,
                successMessage = null,
                errorMessage = null,
            )
        }
    }

    fun setRequestedOutcome(requestedOutcome: String) {
        _uiState.update { state -> state.copy(requestedOutcome = requestedOutcome) }
    }

    fun toggleIssue(issueType: String, enabled: Boolean) {
        _uiState.update { state ->
            state.copy(
                editableIssues = state.editableIssues.map { issue ->
                    if (issue.issueType == issueType) issue.copy(enabled = enabled) else issue
                },
            )
        }
    }

    fun updateIssueComment(issueType: String, comment: String) {
        _uiState.update { state ->
            state.copy(
                editableIssues = state.editableIssues.map { issue ->
                    if (issue.issueType == issueType) issue.copy(comment = comment) else issue
                },
            )
        }
    }

    fun analyzeCurrentUrl() {
        val targetUrl = _uiState.value.currentUrl.trim()
        if (targetUrl.isBlank()) {
            _uiState.update { state -> state.copy(errorMessage = "Paste or share a YouTube URL first.") }
            return
        }
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    loading = true,
                    errorMessage = null,
                    successMessage = null,
                    statusLines = listOf("Sending analyze request to TruthLens API…"),
                )
            }
            runCatching {
                repository.api(_uiState.value.settings).analyzeShare(
                    MobileAnalyzeShareRequestDto(
                        targetUrl = targetUrl,
                        userContext = UserContextDto(),
                    ),
                )
            }.onSuccess { response ->
                val workflowMode = response.reviewPrompt?.workflowMode ?: "report"
                val editableIssues = response.draftSuggestion.issues.map { issue ->
                    EditableIssue(
                        issueType = issue.issueType,
                        label = issueLabel(issue.issueType),
                        enabled = issue.suggested,
                        comment = issue.comment,
                    )
                }
                val initialState = MainUiState(
                    currentUrl = targetUrl,
                    settings = _uiState.value.settings,
                    analysis = response,
                    workflowMode = workflowMode,
                    requestedOutcome = response.draftSuggestion.suggestedOutcome,
                    editableIssues = editableIssues,
                    optimizedReportText = buildReportText(
                        workflowMode = workflowMode,
                        requestedOutcome = response.draftSuggestion.suggestedOutcome,
                        title = response.watchContext.title,
                        issues = editableIssues,
                    ),
                    optimizationModel = response.draftSuggestion.suggestionModel,
                    recentAnalyses = _uiState.value.recentAnalyses,
                    loading = false,
                    submitting = false,
                    statusLines = response.statusStream.map { it.label + (it.details?.let { details -> " $details" } ?: "") },
                    errorMessage = null,
                    successMessage = "Analysis complete.",
                )
                _uiState.value = initialState
                settingsStore.prependRecent(
                    RecentAnalysisEntry(
                        targetUrl = response.watchContext.targetUrl,
                        title = response.watchContext.title,
                        score = response.score.riskScore,
                        recommendedAction = response.score.recommendedAction,
                        summary = response.explanation.explanationSummary ?: "",
                        timestampIso = OffsetDateTime.now(ZoneOffset.UTC).toString(),
                    ),
                )
                if (_uiState.value.settings.autoOptimizeDrafts) {
                    optimizeDrafts()
                }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(
                        loading = false,
                        errorMessage = error.message ?: "Analyze request failed.",
                        statusLines = it.statusLines + "Analyze request failed.",
                    )
                }
            }
        }
    }

    fun optimizeDrafts() {
        val state = _uiState.value
        val analysis = state.analysis ?: return
        val selectedIssues = selectedIssues()
        if (selectedIssues.isEmpty()) {
            _uiState.update { current ->
                current.copy(errorMessage = "Select at least one issue before optimizing.")
            }
            return
        }
        viewModelScope.launch {
            _uiState.update { current ->
                current.copy(loading = true, statusLines = current.statusLines + "Optimizing draft comments…")
            }
            runCatching {
                repository.api(_uiState.value.settings).optimizeReport(
                    ManualReportOptimizationRequestDto(
                        workflowMode = _uiState.value.workflowMode,
                        targetUrl = analysis.watchContext.targetUrl,
                        titleSnapshot = analysis.watchContext.title,
                        channelName = analysis.watchContext.channelName,
                        transcriptExcerpt = analysis.watchContext.transcriptExcerpt,
                        requestedOutcome = _uiState.value.requestedOutcome,
                        issues = selectedIssues,
                    ),
                )
            }.onSuccess { optimized ->
                _uiState.update { current ->
                    current.copy(
                        loading = false,
                        editableIssues = current.editableIssues.map { issue ->
                            val replacement = optimized.issues.firstOrNull { it.issueType == issue.issueType }
                            if (replacement != null) {
                                issue.copy(comment = replacement.comment)
                            } else {
                                issue
                            }
                        },
                        optimizedReportText = optimized.reportText,
                        optimizationModel = optimized.optimizationModel,
                        successMessage = "Draft comments optimized.",
                        statusLines = current.statusLines + "Draft comments optimized.",
                    )
                }
            }.onFailure { error ->
                _uiState.update { current ->
                    current.copy(
                        loading = false,
                        errorMessage = error.message ?: "Optimization failed.",
                        statusLines = current.statusLines + "Optimization failed.",
                    )
                }
            }
        }
    }

    fun submitCurrentReview() {
        val state = _uiState.value
        val analysis = state.analysis ?: return
        val selectedIssues = selectedIssues()
        if (selectedIssues.isEmpty()) {
            _uiState.update { current -> current.copy(errorMessage = "Select at least one issue before submitting.") }
            return
        }
        val reportText = if (state.optimizedReportText.isNotBlank()) {
            state.optimizedReportText
        } else {
            buildReportText(
                workflowMode = state.workflowMode,
                requestedOutcome = state.requestedOutcome,
                title = analysis.watchContext.title,
                issues = state.editableIssues,
            )
        }
        viewModelScope.launch {
            _uiState.update { current ->
                current.copy(submitting = true, errorMessage = null, successMessage = null)
            }
            runCatching {
                val api = repository.api(_uiState.value.settings)
                var reportMessage = ""
                if (state.workflowMode == "report" && analysis.youTubeAuth.connected) {
                    val youtubeResponse = api.submitYouTubeReport(
                        YouTubeReportRequestDto(
                            targetUrl = analysis.watchContext.targetUrl,
                            reportText = reportText,
                            issueTypes = selectedIssues.map { it.issueType },
                        ),
                    )
                    reportMessage = "Reported to YouTube under ${youtubeResponse.reasonLabel}."
                }
                api.submitFeedback(
                    FeedbackEventDto(
                        itemId = analysis.watchContext.videoId,
                        itemHash = null,
                        channelName = analysis.watchContext.channelName,
                        modelVersion = analysis.modelVersion,
                        policyVersion = analysis.policyVersion,
                        actionShown = analysis.score.recommendedAction,
                        userAction = if (state.workflowMode == "verify-transparent") "confirm-transparent" else "confirm-report",
                        explanationId = analysis.score.explanationId,
                        beforeScore = analysis.score.riskScore,
                        afterScore = if (state.workflowMode == "verify-transparent") 0.05 else analysis.score.riskScore,
                        timestamp = OffsetDateTime.now(ZoneOffset.UTC).toString(),
                        manualReport = ManualReportDto(
                            workflowMode = state.workflowMode,
                            targetUrl = analysis.watchContext.targetUrl,
                            thumbnailRef = analysis.watchContext.thumbnailRef,
                            titleSnapshot = analysis.watchContext.title,
                            transcriptExcerpt = analysis.watchContext.transcriptExcerpt,
                            issues = selectedIssues,
                            requestedOutcome = state.requestedOutcome,
                            optimizeRequested = state.settings.autoOptimizeDrafts,
                            optimizeApplied = state.optimizationModel != null,
                            optimizationModel = state.optimizationModel,
                            reportText = reportText,
                        ),
                    ),
                )
                reportMessage.ifBlank {
                    if (state.workflowMode == "verify-transparent") {
                        "Transparent verification saved to TruthLens."
                    } else {
                        "TruthLens feedback saved locally."
                    }
                }
            }.onSuccess { message ->
                _uiState.update { current ->
                    current.copy(
                        submitting = false,
                        successMessage = message,
                        statusLines = current.statusLines + message,
                    )
                }
            }.onFailure { error ->
                _uiState.update { current ->
                    current.copy(
                        submitting = false,
                        errorMessage = error.message ?: "Submission failed.",
                        statusLines = current.statusLines + "Submission failed.",
                    )
                }
            }
        }
    }

    fun currentAuthUrl(): String? = _uiState.value.analysis?.youTubeAuth?.authUrl

    private fun selectedIssues(): List<ManualReportIssueDto> {
        return _uiState.value.editableIssues
            .filter { it.enabled && it.comment.isNotBlank() }
            .map { issue ->
                ManualReportIssueDto(
                    issueType = issue.issueType,
                    comment = issue.comment.trim(),
                    originalComment = null,
                )
            }
    }

    private fun buildReportText(
        workflowMode: String,
        requestedOutcome: String,
        title: String,
        issues: List<EditableIssue>,
    ): String {
        val enabledIssues = issues.filter { it.enabled && it.comment.isNotBlank() }
        val openingLine = if (workflowMode == "verify-transparent") {
            "Video \"$title\" appears transparently presented."
        } else {
            "Requesting $requestedOutcome review for video \"$title\"."
        }
        return buildString {
            appendLine(openingLine)
            enabledIssues.forEach { issue ->
                appendLine("${issue.label}: ${issue.comment.trim()}")
            }
        }.trim()
    }

    private fun issueLabel(issueType: String): String {
        return when (issueType) {
            "thumbnail" -> "Thumbnail"
            "title" -> "Title"
            "description" -> "Description"
            "transcript" -> "Transcript"
            "channel" -> "Channel"
            else -> "Other"
        }
    }
}
