import { useEffect, useRef, useState } from 'react';
import type {
  FeedbackEvent,
  ManualReportIssueType,
  ManualReportRequestedOutcome,
  YouTubeAuthStatus,
} from '@truthlens/shared-schemas';

import {
  fetchYouTubeAuthStatus,
  optimizeManualReportComments,
  sendFeedbackEvent,
  suggestManualReportComments,
  submitYouTubeReport,
} from '../lib/api';
import { fetchYouTubeWatchMetadata } from '../lib/youtubeWatchMetadata';
import { submitYouTubePageReport } from '../lib/youtubePageReporting';
import { useOverlayStore } from './store';

const ISSUE_OPTIONS: Array<{ issueType: ManualReportIssueType; label: string }> = [
  { issueType: 'thumbnail', label: 'Thumbnail' },
  { issueType: 'title', label: 'Title' },
  { issueType: 'description', label: 'Description' },
  { issueType: 'transcript', label: 'Transcript' },
  { issueType: 'channel', label: 'Channel' },
  { issueType: 'other', label: 'Other' },
];

type SelectedIssueState = Record<ManualReportIssueType, boolean>;
type IssueCommentState = Record<ManualReportIssueType, string>;
type LiveStatusTone = 'info' | 'success' | 'error';

type LiveStatusEntry = {
  id: number;
  message: string;
  tone: LiveStatusTone;
};

const DEFAULT_SELECTED_ISSUES: SelectedIssueState = {
  thumbnail: false,
  title: false,
  description: false,
  transcript: false,
  channel: false,
  other: false,
};

const DEFAULT_COMMENTS: IssueCommentState = {
  thumbnail: '',
  title: '',
  description: '',
  transcript: '',
  channel: '',
  other: '',
};

function createFeedbackPayload(
  itemId: string,
  channelName: string,
  actionShown: FeedbackEvent['action_shown'],
  beforeScore: number | null,
  explanationId: string | null,
  manualReport: FeedbackEvent['manual_report'],
  userAction: FeedbackEvent['user_action'],
): FeedbackEvent {
  return {
    item_id: itemId,
    item_hash: null,
    channel_name: channelName,
    model_version: 'extension-runtime',
    policy_version: 'adaptive-threshold-v1',
    action_shown: actionShown,
    user_action: userAction,
    explanation_id: explanationId,
    before_score: beforeScore,
    after_score: beforeScore,
    timestamp: new Date().toISOString(),
    manual_report: manualReport,
  };
}

function buildDraftReportText(
  title: string,
  channelName: string,
  requestedOutcome: ManualReportRequestedOutcome,
  issues: Array<{ label: string; comment: string }>,
): string {
  const openingLine =
    requestedOutcome === 'remove'
      ? 'Requested action: Please remove this content because the presentation appears materially misleading.'
      : 'Requested action: Please moderate this content so the presentation becomes consistent and non-misleading.';
  const lines = [
    openingLine,
    `Video: "${title}"`,
    `Channel: ${channelName}`,
    '',
    'Requested review for potentially misleading presentation in these areas:',
    ...issues.map((issue) => `- ${issue.label}: ${issue.comment}`),
  ];

  return lines.join('\n').trim();
}

function requestedOutcomeLabel(value: ManualReportRequestedOutcome): string {
  return value === 'remove' ? 'Remove' : 'Moderate';
}

function shouldUsePageReportFallback(message: string): boolean {
  return message.includes("did not return a suitable 'Spam or misleading' report category");
}

async function openTargetUrl(url: string | null): Promise<void> {
  if (!url) {
    return;
  }
  if (typeof chrome !== 'undefined' && chrome.runtime?.sendMessage) {
    try {
      await chrome.runtime.sendMessage({ type: 'TRUTHLENS_OPEN_REPORT_TARGET', url });
      return;
    } catch {
      // Fall back to window.open if the extension runtime is unavailable in the current test/runtime.
    }
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}

export function App() {
  const { manualReportTarget, closeManualReport } = useOverlayStore();
  const [selectedIssues, setSelectedIssues] = useState<SelectedIssueState>(DEFAULT_SELECTED_ISSUES);
  const [comments, setComments] = useState<IssueCommentState>(DEFAULT_COMMENTS);
  const [originalComments, setOriginalComments] = useState<Partial<IssueCommentState>>({});
  const [optimizeChoice, setOptimizeChoice] = useState<'yes' | 'no'>('no');
  const [requestedOutcome, setRequestedOutcome] =
    useState<ManualReportRequestedOutcome>('moderate');
  const [optimizationApplied, setOptimizationApplied] = useState(false);
  const [optimizationModel, setOptimizationModel] = useState<string | null>(null);
  const [optimizedReportText, setOptimizedReportText] = useState<string | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingDrafts, setIsLoadingDrafts] = useState(false);
  const [draftModel, setDraftModel] = useState<string | null>(null);
  const [isLoadingYouTubeStatus, setIsLoadingYouTubeStatus] = useState(false);
  const [youtubeAuthStatus, setYouTubeAuthStatus] = useState<YouTubeAuthStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [statusEntries, setStatusEntries] = useState<LiveStatusEntry[]>([]);
  const [submissionCompleted, setSubmissionCompleted] = useState(false);
  const statusIdRef = useRef(0);

  function appendStatusLine(message: string, tone: LiveStatusTone = 'info') {
    setStatusEntries((current) => {
      const last = current.at(-1);
      if (last?.message === message && last.tone === tone) {
        return current;
      }

      statusIdRef.current += 1;
      return [...current.slice(-5), { id: statusIdRef.current, message, tone }];
    });
  }

  useEffect(() => {
    statusIdRef.current = manualReportTarget ? 1 : 0;
    setSelectedIssues(DEFAULT_SELECTED_ISSUES);
    setComments(DEFAULT_COMMENTS);
    setOriginalComments({});
    setOptimizeChoice('no');
    setRequestedOutcome('moderate');
    setOptimizationApplied(false);
    setOptimizationModel(null);
    setOptimizedReportText(null);
    setIsOptimizing(false);
    setIsSubmitting(false);
    setIsLoadingDrafts(false);
    setDraftModel(null);
    setIsLoadingYouTubeStatus(false);
    setYouTubeAuthStatus(null);
    setErrorMessage(null);
    setSuccessMessage(null);
    setSubmissionCompleted(false);
    setStatusEntries(
      manualReportTarget
        ? [
            {
              id: 1,
              message:
                manualReportTarget.workflowMode === 'verify-transparent'
                  ? 'Preparing TruthLens transparency verification…'
                  : 'Preparing TruthLens report analysis…',
              tone: 'info',
            },
          ]
        : [],
    );
  }, [manualReportTarget]);

  useEffect(() => {
    if (!manualReportTarget) {
      return;
    }

    let cancelled = false;
    setIsLoadingDrafts(true);
    if (manualReportTarget.workflowMode !== 'verify-transparent') {
      setIsLoadingYouTubeStatus(true);
      appendStatusLine('Checking YouTube reporting connection…');
      void fetchYouTubeAuthStatus()
        .then((status) => {
          if (cancelled) {
            return;
          }
          setYouTubeAuthStatus(status);
          appendStatusLine(
            status.connected
              ? `YouTube direct reporting is connected${status.channel_name ? ` as ${status.channel_name}` : ''}.`
              : status.configured
                ? 'YouTube reporting is configured but still needs account authorization.'
                : 'YouTube direct reporting is not configured in the local API.',
            status.connected ? 'success' : 'info',
          );
        })
        .catch(() => {
          if (cancelled) {
            return;
          }
          setErrorMessage('Could not load YouTube reporting status from the local API.');
          appendStatusLine('Could not load YouTube reporting status from the local API.', 'error');
        })
        .finally(() => {
          if (!cancelled) {
            setIsLoadingYouTubeStatus(false);
          }
        });
    } else {
      setIsLoadingYouTubeStatus(false);
      setYouTubeAuthStatus(null);
      appendStatusLine('Loading local transparency evidence for this video…');
    }

    void (async () => {
      appendStatusLine('Loading watch metadata and transcript context…');
      const enrichedMetadata = manualReportTarget.linkUrl
        ? await fetchYouTubeWatchMetadata(
            manualReportTarget.linkUrl,
            fetch,
            manualReportTarget.channelUrl,
          )
        : {
            descriptionSnapshot: null,
            transcriptExcerpt: null,
            transcriptAvailable: null,
            channelUrl: null,
            channelContext: null,
          };
      const descriptionSnapshot =
        enrichedMetadata.descriptionSnapshot ?? manualReportTarget.descriptionSnapshot;
      const transcriptExcerpt =
        enrichedMetadata.transcriptExcerpt ?? manualReportTarget.transcriptExcerpt;
      const transcriptAvailable = enrichedMetadata.transcriptAvailable;
      const channelUrl = enrichedMetadata.channelUrl ?? manualReportTarget.channelUrl;
      appendStatusLine('Drafting initial comments with Gemini…');

      return suggestManualReportComments({
        workflow_mode: manualReportTarget.workflowMode,
        target_url: manualReportTarget.linkUrl,
        thumbnail_ref: manualReportTarget.thumbnailRef,
        title_snapshot: manualReportTarget.title,
        channel_name: manualReportTarget.channelName,
        channel_url: channelUrl,
        channel_context: enrichedMetadata.channelContext,
        description_snapshot: descriptionSnapshot,
        transcript_excerpt:
          transcriptExcerpt && transcriptExcerpt !== descriptionSnapshot ? transcriptExcerpt : null,
        transcript_available: transcriptAvailable,
        explanation_summary: manualReportTarget.score?.explanation_summary ?? null,
        reasons: manualReportTarget.score?.reasons ?? [],
      });
    })()
      .then((draft) => {
        if (cancelled) {
          return;
        }
        const nextSelected = { ...DEFAULT_SELECTED_ISSUES };
        const nextComments = { ...DEFAULT_COMMENTS };
        for (const issue of draft.issues) {
          nextSelected[issue.issue_type] = issue.suggested;
          nextComments[issue.issue_type] = issue.suggested ? issue.comment : '';
        }
        setSelectedIssues(nextSelected);
        setComments(nextComments);
        setRequestedOutcome(draft.suggested_outcome);
        setDraftModel(draft.suggestion_model);
        appendStatusLine('Initial draft suggestions are ready for review.', 'success');
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setDraftModel(null);
        appendStatusLine(
          error instanceof Error
            ? `Automatic draft suggestions were not available: ${error.message}`
            : 'Automatic draft suggestions were not available. You can still write comments manually.',
          'error',
        );
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingDrafts(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [manualReportTarget]);

  useEffect(() => {
    if (!manualReportTarget || !submissionCompleted) {
      return;
    }

    const closeTimer = window.setTimeout(() => {
      closeManualReport();
    }, 1600);

    return () => {
      window.clearTimeout(closeTimer);
    };
  }, [closeManualReport, manualReportTarget, submissionCompleted]);

  const activeIssues = ISSUE_OPTIONS.filter(({ issueType }) => selectedIssues[issueType]).map(
    ({ issueType, label }) => ({
      issueType,
      label,
      comment: comments[issueType].trim(),
    }),
  );
  const missingComments = activeIssues.some((issue) => issue.comment.length === 0);
  const previewText = manualReportTarget
    ? optimizationApplied && optimizedReportText
      ? optimizedReportText
      : buildDraftReportText(
          manualReportTarget.title,
          manualReportTarget.channelName,
          requestedOutcome,
          activeIssues,
        )
    : '';
  const canSubmit =
    manualReportTarget !== null &&
    activeIssues.length > 0 &&
    !missingComments &&
    (!manualReportTarget || optimizeChoice === 'no' || optimizationApplied) &&
    (manualReportTarget?.workflowMode === 'verify-transparent' ||
      (Boolean(manualReportTarget?.linkUrl) && youtubeAuthStatus?.connected === true));

  function clearOptimizationState() {
    setOptimizationApplied(false);
    setOptimizationModel(null);
    setOptimizedReportText(null);
    setOriginalComments({});
  }

  async function handleOptimize() {
    if (!manualReportTarget || activeIssues.length === 0 || missingComments) {
      setErrorMessage('V\u00e6lg mindst \u00e9t punkt og skriv en kort kommentar til hver valgt fejl.');
      return;
    }
    setIsOptimizing(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    appendStatusLine('Sending selected comments to Gemini for optimization…');
    try {
      const response = await optimizeManualReportComments({
        workflow_mode: manualReportTarget.workflowMode,
        target_url: manualReportTarget.linkUrl,
        title_snapshot: manualReportTarget.title,
        channel_name: manualReportTarget.channelName,
        transcript_excerpt: manualReportTarget.transcriptExcerpt,
        requested_outcome: requestedOutcome,
        issues: activeIssues.map((issue) => ({
          issue_type: issue.issueType,
          comment: issue.comment,
        })),
      });
      const nextComments = { ...comments };
      const nextOriginalComments: Partial<IssueCommentState> = {};
      for (const issue of response.issues) {
        nextOriginalComments[issue.issue_type] = comments[issue.issue_type];
        nextComments[issue.issue_type] = issue.comment;
      }
      setComments(nextComments);
      setOriginalComments(nextOriginalComments);
      setOptimizationApplied(true);
      setOptimizationModel(response.optimization_model);
      setOptimizedReportText(response.report_text);
      const usedHeuristicOptimization = response.optimization_model.startsWith('truthlens-heuristic-');
      setSuccessMessage(
        usedHeuristicOptimization
          ? 'Gemini var rate-limited, så TruthLens brugte lokal kommentaroptimering og opdaterede previewet.'
          : 'Kommentarerne blev optimeret og vist i previewen.',
      );
      appendStatusLine(
        usedHeuristicOptimization
          ? 'Gemini was rate-limited, so TruthLens applied local optimization and refreshed the preview.'
          : 'Comment optimization completed and the preview was refreshed.',
        'success',
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Gemini-optimering fejlede.');
      appendStatusLine(
        error instanceof Error ? error.message : 'Gemini optimization failed.',
        'error',
      );
    } finally {
      setIsOptimizing(false);
    }
  }

  async function handleSubmit() {
    if (!manualReportTarget || !canSubmit) {
      setErrorMessage(
        'Rapporten kr\u00e6ver mindst \u00e9n udfyldt fejlbeskrivelse og en aktiv YouTube-forbindelse.',
      );
      return;
    }
    if (!manualReportTarget.linkUrl) {
      setErrorMessage('TruthLens could not determine a YouTube video URL for this report.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setSubmissionCompleted(false);
    const manualReport = {
      workflow_mode: manualReportTarget.workflowMode,
      target_url: manualReportTarget.linkUrl,
      thumbnail_ref: manualReportTarget.thumbnailRef,
      title_snapshot: manualReportTarget.title,
      transcript_excerpt: manualReportTarget.transcriptExcerpt,
      issues: activeIssues.map((issue) => ({
        issue_type: issue.issueType,
        comment: comments[issue.issueType].trim(),
        original_comment: originalComments[issue.issueType] ?? null,
      })),
      requested_outcome: requestedOutcome,
      optimize_requested: optimizeChoice === 'yes',
      optimize_applied: optimizationApplied,
      optimization_model: optimizationModel,
      report_text: previewText,
    } as const;

    try {
      let successText: string;
      if (manualReportTarget.workflowMode === 'verify-transparent') {
        appendStatusLine('Saving a positive transparency verification to TruthLens…');
        successText =
          'Den positive transparens-verifikation blev gemt lokalt som TruthLens-feedback.';
      } else {
        appendStatusLine('Submitting the report to YouTube…');
        const issueTypes = activeIssues.map((issue) => issue.issueType);
        try {
          const youtubeReport = await submitYouTubeReport({
            target_url: manualReportTarget.linkUrl,
            report_text: previewText,
            issue_types: issueTypes,
          });
          successText = youtubeReport.secondary_reason_label
            ? `Rapporten blev sendt direkte til YouTube under "${youtubeReport.reason_label}" / "${youtubeReport.secondary_reason_label}"`
            : `Rapporten blev sendt direkte til YouTube under "${youtubeReport.reason_label}"`;
          appendStatusLine('YouTube accepted the direct TruthLens report.', 'success');
        } catch (error) {
          const detail =
            error instanceof Error ? error.message : 'Rapporten kunne ikke sendes lige nu.';
          if (!shouldUsePageReportFallback(detail)) {
            throw error;
          }

          appendStatusLine(
            'Direct YouTube API reporting was unavailable, so TruthLens is trying the in-page report flow…',
          );
          const youtubePageReport = await submitYouTubePageReport(manualReportTarget, issueTypes);
          successText = youtubePageReport.secondary_reason_label
            ? `Rapporten blev sendt via YouTubes indbyggede report-flow under "${youtubePageReport.reason_label}" / "${youtubePageReport.secondary_reason_label}"`
            : `Rapporten blev sendt via YouTubes indbyggede report-flow under "${youtubePageReport.reason_label}"`;
          appendStatusLine('The in-page YouTube report flow completed successfully.', 'success');
        }
      }

      await sendFeedbackEvent(
        createFeedbackPayload(
          manualReportTarget.itemId,
          manualReportTarget.channelName,
          manualReportTarget.score?.recommended_action ?? 'none',
          manualReportTarget.score?.risk_score ?? null,
          manualReportTarget.score?.explanation_id ?? null,
          manualReport,
          manualReportTarget.workflowMode === 'verify-transparent'
            ? 'confirm-transparent'
            : 'confirm-report',
          ),
      );
      appendStatusLine('TruthLens feedback was stored locally.', 'success');
      setSuccessMessage(
        manualReportTarget.workflowMode === 'verify-transparent'
          ? successText
          : `${successText}, og TruthLens-feedback blev gemt lokalt.`,
      );
      appendStatusLine('Closing the sheet in a moment…', 'success');
      setSubmissionCompleted(true);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : 'Rapporten kunne ikke sendes lige nu.',
      );
      appendStatusLine(
        error instanceof Error ? error.message : 'The report could not be completed right now.',
        'error',
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConnectYouTube() {
    const authUrl = youtubeAuthStatus?.auth_url ?? 'http://127.0.0.1:8000/youtube/auth/start';
    setErrorMessage(null);
    setSuccessMessage(null);
    appendStatusLine('Opening the YouTube authorization flow…');
    await openTargetUrl(authUrl);
  }

  return (
    <>
      {manualReportTarget ? (
        <section className="truthlens-report-sheet" aria-label="TruthLens manual report">
          <div className="truthlens-report-card">
            <div className="truthlens-report-header">
              <div>
              <p className="truthlens-report-kicker">
                {manualReportTarget.workflowMode === 'verify-transparent'
                  ? 'Transparency verification'
                  : 'Manual report'}
              </p>
                <h2>{manualReportTarget.title}</h2>
                <p className="truthlens-report-channel">{manualReportTarget.channelName}</p>
              </div>
              <button
                className="truthlens-close-button"
                type="button"
                onClick={closeManualReport}
              >
                Close
              </button>
            </div>

            <p className="truthlens-report-intro">
              {manualReportTarget.workflowMode === 'verify-transparent'
                ? 'Mark what appears transparent and consistent. A note field appears under each checked area.'
                : 'Mark what looks wrong. A note field appears under each checked issue.'}
            </p>

            <div className="truthlens-live-status" aria-live="polite" aria-atomic="false">
              <p className="truthlens-preview-label">Live status</p>
              <ul className="truthlens-live-status-list">
                {statusEntries.map((entry) => (
                  <li
                    className={`truthlens-live-status-item truthlens-live-status-item-${entry.tone}`}
                    key={entry.id}
                  >
                    {entry.message}
                  </li>
                ))}
              </ul>
            </div>

            <div className="truthlens-report-grid">
              {ISSUE_OPTIONS.map(({ issueType, label }) => (
                <label className="truthlens-issue-card" key={issueType}>
                  <span className="truthlens-issue-toggle">
                    <input
                      checked={selectedIssues[issueType]}
                      onChange={(event) => {
                        setSelectedIssues((state) => ({
                          ...state,
                          [issueType]: event.target.checked,
                        }));
                        clearOptimizationState();
                        setErrorMessage(null);
                        setSuccessMessage(null);
                      }}
                      type="checkbox"
                    />
                    <span>{label}</span>
                  </span>
                  {selectedIssues[issueType] ? (
                    <textarea
                      className="truthlens-issue-comment"
                      onChange={(event) => {
                        setComments((state) => ({
                          ...state,
                          [issueType]: event.target.value,
                        }));
                        clearOptimizationState();
                        setErrorMessage(null);
                        setSuccessMessage(null);
                      }}
                      placeholder={`Describe the ${label.toLowerCase()} issue briefly.`}
                      rows={3}
                      value={comments[issueType]}
                    />
                  ) : null}
                </label>
              ))}
            </div>

            {manualReportTarget.workflowMode !== 'verify-transparent' ? (
              <fieldset className="truthlens-optimize-choice">
                <legend>Requested outcome</legend>
                <label>
                  <input
                    checked={requestedOutcome === 'moderate'}
                    name="truthlens-requested-outcome"
                    onChange={() => {
                      setRequestedOutcome('moderate');
                      clearOptimizationState();
                      setErrorMessage(null);
                      setSuccessMessage(null);
                    }}
                    type="radio"
                  />
                  <span>Moderate</span>
                </label>
                <label>
                  <input
                    checked={requestedOutcome === 'remove'}
                    name="truthlens-requested-outcome"
                    onChange={() => {
                      setRequestedOutcome('remove');
                      clearOptimizationState();
                      setErrorMessage(null);
                      setSuccessMessage(null);
                    }}
                    type="radio"
                  />
                  <span>Remove</span>
                </label>
              </fieldset>
            ) : null}

            <fieldset className="truthlens-optimize-choice">
              <legend>Optimize wording with Gemini?</legend>
              <label>
                <input
                  checked={optimizeChoice === 'yes'}
                  name="truthlens-optimize-choice"
                  onChange={() => {
                    setOptimizeChoice('yes');
                    setErrorMessage(null);
                    setSuccessMessage(null);
                  }}
                  type="radio"
                />
                <span>Yes</span>
              </label>
              <label>
                <input
                  checked={optimizeChoice === 'no'}
                  name="truthlens-optimize-choice"
                  onChange={() => {
                    setOptimizeChoice('no');
                    clearOptimizationState();
                    setErrorMessage(null);
                    setSuccessMessage(null);
                  }}
                  type="radio"
                />
                <span>No</span>
              </label>
            </fieldset>

            {optimizeChoice === 'yes' ? (
              <button
                className="truthlens-secondary-button"
                disabled={isOptimizing || activeIssues.length === 0 || missingComments}
                onClick={() => {
                  void handleOptimize();
                }}
                type="button"
              >
                {isOptimizing ? 'Optimizing...' : 'Optimize comments'}
              </button>
            ) : null}

            {manualReportTarget.workflowMode !== 'verify-transparent' ? (
              <div className="truthlens-platform-status">
                <p className="truthlens-preview-label">YouTube reporting</p>
                {isLoadingYouTubeStatus ? (
                  <p className="truthlens-preview-empty">Checking local YouTube connection...</p>
                ) : youtubeAuthStatus?.connected ? (
                  <p className="truthlens-platform-message">
                    Direct reporting is connected
                    {youtubeAuthStatus.channel_name ? ` as ${youtubeAuthStatus.channel_name}` : ''}. If
                    the YouTube API does not expose a misleading category for this account, TruthLens
                    will fall back to YouTube&apos;s in-page report flow on the current feed card.
                  </p>
                ) : youtubeAuthStatus?.configured ? (
                  <>
                    <p className="truthlens-platform-message">
                      Connect your YouTube account once to let TruthLens submit reports without
                      opening the video page.
                    </p>
                    <button
                      className="truthlens-secondary-button"
                      onClick={() => {
                        void handleConnectYouTube();
                      }}
                      type="button"
                    >
                      Connect YouTube
                    </button>
                  </>
                ) : (
                  <p className="truthlens-platform-message">
                    Add <code>TRUTHLENS_YOUTUBE_CLIENT_ID</code>,{' '}
                    <code>TRUTHLENS_YOUTUBE_CLIENT_SECRET</code>, and{' '}
                    <code>TRUTHLENS_YOUTUBE_REDIRECT_URI</code> to <code>.env</code>, then restart
                    the API.
                  </p>
                )}
              </div>
            ) : null}

            <div className="truthlens-report-preview">
              <p className="truthlens-preview-label">Report preview</p>
              {manualReportTarget ? (
                <>
                  <div className="truthlens-preview-section">
                    <p className="truthlens-preview-section-title">Video</p>
                    <p className="truthlens-preview-title">{manualReportTarget.title}</p>
                    <p className="truthlens-preview-channel">{manualReportTarget.channelName}</p>
                  </div>

                  <div className="truthlens-preview-section">
                    <p className="truthlens-preview-section-title">Requested outcome</p>
                    <p className="truthlens-preview-channel">
                      {manualReportTarget.workflowMode === 'verify-transparent'
                        ? 'Transparent / non-clickbait verification'
                        : requestedOutcomeLabel(requestedOutcome)}
                    </p>
                  </div>

                  <div className="truthlens-preview-section">
                    <p className="truthlens-preview-section-title">Selected issues</p>
                    {activeIssues.length > 0 ? (
                      <ul className="truthlens-preview-issue-list">
                        {activeIssues.map((issue) => (
                          <li className="truthlens-preview-issue-item" key={issue.issueType}>
                            <p className="truthlens-preview-issue-label">{issue.label}</p>
                            <p className="truthlens-preview-issue-comment">{issue.comment}</p>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="truthlens-preview-empty">
                        Select one or more issue types to build a report preview.
                      </p>
                    )}
                  </div>

                  <div className="truthlens-preview-section">
                    <p className="truthlens-preview-section-title">Submission text</p>
                    <pre className="truthlens-preview-text">
                      {previewText || 'Select one or more issue types to build a report preview.'}
                    </pre>
                  </div>
                </>
              ) : (
                <p className="truthlens-preview-empty">
                  Select one or more issue types to build a report preview.
                </p>
              )}
              {optimizationApplied && optimizationModel ? (
                <p className="truthlens-preview-meta">Optimized with {optimizationModel}</p>
              ) : null}
              {isLoadingDrafts ? (
                <p className="truthlens-preview-meta">Drafting initial suggestions with Gemini...</p>
              ) : null}
              {!isLoadingDrafts && draftModel ? (
                <p className="truthlens-preview-meta">
                  Initial draft suggestions prepared with {draftModel}
                </p>
              ) : null}
            </div>

            {errorMessage ? <p className="truthlens-status truthlens-status-error">{errorMessage}</p> : null}
            {successMessage ? (
              <p className="truthlens-status truthlens-status-success">{successMessage}</p>
            ) : null}

            <div className="truthlens-report-actions">
              <button
                className="truthlens-primary-button"
                disabled={!canSubmit || isSubmitting}
                onClick={() => {
                  void handleSubmit();
                }}
                type="button"
              >
                {isSubmitting
                  ? manualReportTarget.workflowMode === 'verify-transparent'
                    ? 'Saving...'
                    : 'Reporting...'
                  : manualReportTarget.workflowMode === 'verify-transparent'
                    ? 'Verify'
                    : 'Report'}
              </button>
              <button
                className="truthlens-secondary-button"
                onClick={closeManualReport}
                type="button"
              >
                Cancel
              </button>
            </div>
          </div>
        </section>
      ) : null}
    </>
  );
}
