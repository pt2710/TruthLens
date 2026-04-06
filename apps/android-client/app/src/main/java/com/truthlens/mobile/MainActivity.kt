package com.truthlens.mobile

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel.ingestSharedText(extractSharedText(intent))
        setContent {
            TruthLensApp(viewModel)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        viewModel.ingestSharedText(extractSharedText(intent))
    }

    private fun extractSharedText(intent: Intent?): String? {
        if (intent == null) return null
        return when (intent.action) {
            Intent.ACTION_SEND -> intent.getStringExtra(Intent.EXTRA_TEXT)
            Intent.ACTION_VIEW -> intent.dataString
            else -> intent.dataString
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TruthLensApp(viewModel: MainViewModel) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    MaterialTheme {
        Scaffold(
            topBar = {
                TopAppBar(title = { Text("TruthLens Mobile") })
            },
        ) { innerPadding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(innerPadding)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                SettingsSection(
                    state = state,
                    onApiBaseUrlChange = viewModel::updateApiBaseUrl,
                    onApiKeyChange = viewModel::updateApiKey,
                    onAutoOptimizeChange = viewModel::toggleAutoOptimize,
                    onShowDebugChange = viewModel::toggleShowDebug,
                    onSave = viewModel::saveSettings,
                )
                AnalyzeSection(
                    url = state.currentUrl,
                    onUrlChange = viewModel::updateCurrentUrl,
                    onAnalyze = viewModel::analyzeCurrentUrl,
                    isLoading = state.loading,
                )
                MessagesSection(
                    errorMessage = state.errorMessage,
                    successMessage = state.successMessage,
                    statusLines = state.statusLines,
                )
                AnalysisSection(
                    state = state,
                    onWorkflowModeChange = viewModel::setWorkflowMode,
                    onRequestedOutcomeChange = viewModel::setRequestedOutcome,
                    onIssueToggle = viewModel::toggleIssue,
                    onIssueCommentChange = viewModel::updateIssueComment,
                    onOptimize = viewModel::optimizeDrafts,
                    onSubmit = viewModel::submitCurrentReview,
                    onConnectYouTube = {
                        viewModel.currentAuthUrl()?.let { authUrl ->
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(authUrl)))
                        }
                    },
                )
                RecentAnalysesSection(
                    recentTitles = state.recentAnalyses.map { "${it.title} (${it.score})" },
                )
            }
        }
    }
}

@Composable
private fun SettingsSection(
    state: MainUiState,
    onApiBaseUrlChange: (String) -> Unit,
    onApiKeyChange: (String) -> Unit,
    onAutoOptimizeChange: (Boolean) -> Unit,
    onShowDebugChange: (Boolean) -> Unit,
    onSave: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Settings", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = state.settings.apiBaseUrl,
                onValueChange = onApiBaseUrlChange,
                label = { Text("API base URL") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.settings.apiKey,
                onValueChange = onApiKeyChange,
                label = { Text("API key (optional)") },
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                Text("Auto-optimize drafts", modifier = Modifier.weight(1f))
                Switch(
                    checked = state.settings.autoOptimizeDrafts,
                    onCheckedChange = onAutoOptimizeChange,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                Text("Show debug info", modifier = Modifier.weight(1f))
                Switch(
                    checked = state.settings.showDebugInfo,
                    onCheckedChange = onShowDebugChange,
                )
            }
            Button(onClick = onSave) {
                Text("Save settings")
            }
        }
    }
}

@Composable
private fun AnalyzeSection(
    url: String,
    onUrlChange: (String) -> Unit,
    onAnalyze: () -> Unit,
    isLoading: Boolean,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Analyze shared YouTube URL", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = url,
                onValueChange = onUrlChange,
                label = { Text("YouTube URL") },
                modifier = Modifier.fillMaxWidth(),
            )
            Button(onClick = onAnalyze, enabled = !isLoading) {
                Text(if (isLoading) "Analyzing…" else "Analyze")
            }
        }
    }
}

@Composable
private fun MessagesSection(
    errorMessage: String?,
    successMessage: String?,
    statusLines: List<String>,
) {
    if (errorMessage == null && successMessage == null && statusLines.isEmpty()) {
        return
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            successMessage?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            statusLines.forEach { line ->
                Text(line, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun AnalysisSection(
    state: MainUiState,
    onWorkflowModeChange: (String) -> Unit,
    onRequestedOutcomeChange: (String) -> Unit,
    onIssueToggle: (String, Boolean) -> Unit,
    onIssueCommentChange: (String, String) -> Unit,
    onOptimize: () -> Unit,
    onSubmit: () -> Unit,
    onConnectYouTube: () -> Unit,
) {
    val analysis = state.analysis ?: return
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(analysis.watchContext.title, style = MaterialTheme.typography.titleMedium)
            Text("Score ${analysis.score.riskScore} • ${analysis.score.recommendedAction}")
            Text(
                "Class ${analysis.score.contentClass} • confidence ${analysis.score.contentClassConfidence}",
                style = MaterialTheme.typography.bodySmall,
            )
            analysis.score.biasProfile.guardrailApplied?.let { guardrail ->
                Text("Guardrail: $guardrail", style = MaterialTheme.typography.bodySmall)
            }
            if (analysis.score.biasProfile.negativeBiases.isNotEmpty()) {
                Text(
                    "Negative bias: ${analysis.score.biasProfile.negativeBiases.joinToString()}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (analysis.score.biasProfile.positiveBiases.isNotEmpty()) {
                Text(
                    "Preserved bias: ${analysis.score.biasProfile.positiveBiases.joinToString()}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Text(analysis.explanation.explanationSummary ?: "No explanation summary.")

            if (state.settings.showDebugInfo) {
                Text("Model ${analysis.modelVersion} • Policy ${analysis.policyVersion}", style = MaterialTheme.typography.bodySmall)
                Text("Confidence ${analysis.score.confidence} • Uncertainty ${analysis.score.uncertainty}", style = MaterialTheme.typography.bodySmall)
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = state.workflowMode == "report",
                    onClick = { onWorkflowModeChange("report") },
                    label = { Text("Report") },
                )
                FilterChip(
                    selected = state.workflowMode == "verify-transparent",
                    onClick = { onWorkflowModeChange("verify-transparent") },
                    label = { Text("Verify") },
                )
            }

            if (state.workflowMode == "report") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = state.requestedOutcome == "moderate",
                        onClick = { onRequestedOutcomeChange("moderate") },
                        label = { Text("Moderate") },
                    )
                    FilterChip(
                        selected = state.requestedOutcome == "remove",
                        onClick = { onRequestedOutcomeChange("remove") },
                        label = { Text("Remove") },
                    )
                }
            }

            state.analysis.reviewPrompt?.let { prompt ->
                Text("Prompt: ${prompt.reason}", style = MaterialTheme.typography.bodySmall)
            }

            if (!analysis.youTubeAuth.connected && analysis.youTubeAuth.authUrl != null) {
                TextButton(onClick = onConnectYouTube) {
                    Text("Connect YouTube")
                }
            }

            state.editableIssues.forEach { issue ->
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        Checkbox(checked = issue.enabled, onCheckedChange = { checked -> onIssueToggle(issue.issueType, checked) })
                        Text(issue.label, modifier = Modifier.padding(top = 12.dp))
                    }
                    if (issue.enabled) {
                        OutlinedTextField(
                            value = issue.comment,
                            onValueChange = { value -> onIssueCommentChange(issue.issueType, value) },
                            label = { Text("${issue.label} note") },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }

            if (state.optimizedReportText.isNotBlank()) {
                Text("Draft preview", style = MaterialTheme.typography.titleSmall)
                Text(state.optimizedReportText)
            }
            state.optimizationModel?.let { Text("Draft source: $it", style = MaterialTheme.typography.bodySmall) }

            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = onOptimize, enabled = !state.loading && !state.submitting) {
                    Text("Optimize")
                }
                Button(onClick = onSubmit, enabled = !state.loading && !state.submitting) {
                    Text(if (state.submitting) "Submitting…" else "Submit")
                }
            }
        }
    }
}

@Composable
private fun RecentAnalysesSection(recentTitles: List<String>) {
    if (recentTitles.isEmpty()) {
        return
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Recent analyses", style = MaterialTheme.typography.titleMedium)
            recentTitles.forEach { title ->
                Text(title, style = MaterialTheme.typography.bodySmall)
            }
            Spacer(modifier = Modifier.height(4.dp))
        }
    }
}
