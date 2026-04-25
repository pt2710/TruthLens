import { useEffect, useRef, useState } from 'react';
import type {
  FeedbackEvent,
  ManualReportIssueType,
  ManualReportRequestedOutcome,
  ManualReviewCollectionScope,
  ManualReviewTag,
  ManualReviewTagSelection,
  YouTubeAuthStatus,
} from '@truthlens/shared-schemas';

import {
  fetchYouTubeAuthStatus,
  optimizeManualReportComments,
  sendFeedbackEvent,
  suggestManualReportComments,
  submitYouTubeReport,
} from '../lib/api';
import { buildTruthLensApiUrl } from '../lib/runtimeConfig';
import { fetchYouTubeWatchMetadata } from '../lib/youtubeWatchMetadata';
import { submitYouTubePageReport } from '../lib/youtubePageReporting';
import { dispatchManualReviewSubmitted } from '../lib/manualReviewEvents';
import { riskScoreAfterReportFeedback } from '../lib/reportFeedbackScoring';
import { type ManualReportTarget, useOverlayStore } from './store';

const ISSUE_OPTIONS: Array<{ issueType: ManualReportIssueType; label: string }> = [
  { issueType: 'thumbnail', label: 'Thumbnail' },
  { issueType: 'title', label: 'Title' },
  { issueType: 'description', label: 'Description' },
  { issueType: 'transcript', label: 'Transcript' },
  { issueType: 'channel', label: 'Channel' },
  { issueType: 'other', label: 'Other' },
];
const TAG_OPTIONS: Array<{ tag: ManualReviewTag; label: string }> = [
  { tag: 'Clickbait', label: 'Clickbait' },
  { tag: 'Music', label: 'Music' },
  { tag: 'Tutorial', label: 'Tutorial' },
  { tag: 'Walkthrough', label: 'Walkthrough' },
  { tag: 'Gaming', label: 'Gaming' },
  { tag: 'News', label: 'News' },
  { tag: 'Documentary', label: 'Documentary' },
  { tag: 'Promo', label: 'Promo' },
  { tag: 'Satire', label: 'Satire' },
  { tag: 'Art', label: 'Art' },
  { tag: 'Unknown', label: 'Unknown' },
];

type SelectedIssueState = Record<ManualReportIssueType, boolean>;
type IssueCommentState = Record<ManualReportIssueType, string>;
type SelectedTagState = Record<ManualReviewTag, boolean>;
type LiveStatusTone = 'info' | 'success' | 'error';

type LiveStatusEntry = {
  id: number;
  message: string;
  tone: LiveStatusTone;
};

type ReviewEvidence = {
  descriptionSnapshot: string | null;
  transcriptExcerpt: string | null;
  transcriptAvailable: boolean | null;
  channelUrl: string | null;
  channelContext: string | null;
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
const DEFAULT_SELECTED_TAGS: SelectedTagState = {
  Clickbait: false,
  Music: false,
  Tutorial: false,
  Walkthrough: false,
  Gaming: false,
  News: false,
  Documentary: false,
  Promo: false,
  Satire: false,
  Art: false,
  Unknown: false,
};

const EMPTY_REVIEW_EVIDENCE: ReviewEvidence = {
  descriptionSnapshot: null,
  transcriptExcerpt: null,
  transcriptAvailable: null,
  channelUrl: null,
  channelContext: null,
};

function reviewEvidenceFromTarget(target: ManualReportTarget | null): ReviewEvidence {
  if (!target) {
    return EMPTY_REVIEW_EVIDENCE;
  }

  return {
    descriptionSnapshot: target.descriptionSnapshot,
    transcriptExcerpt: target.transcriptExcerpt,
    transcriptAvailable: target.transcriptExcerpt ? true : null,
    channelUrl: target.channelUrl,
    channelContext: null,
  };
}

function createClientId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createFeedbackPayload(
  itemId: string,
  channelName: string,
  actionShown: FeedbackEvent['action_shown'],
  beforeScore: number | null,
  explanationId: string | null,
  manualReport: FeedbackEvent['manual_report'],
  userAction: FeedbackEvent['user_action'],
  artifactProvenance: FeedbackEvent['artifact_provenance'],
  afterScore: number | null = beforeScore,
): FeedbackEvent {
  return {
    feedback_id: createClientId('feedback'),
    item_id: itemId,
    item_hash: null,
    channel_name: channelName,
    model_version: 'extension-runtime',
    policy_version: 'adaptive-threshold-v1',
    action_shown: actionShown,
    user_action: userAction,
    explanation_id: explanationId,
    before_score: beforeScore,
    after_score: afterScore,
    timestamp: new Date().toISOString(),
    runtime_context: {
      surface: 'extension-watch',
      review_requested: true,
      source_provenance: window.location.pathname,
    },
    artifact_provenance: artifactProvenance,
    manual_report: manualReport,
  };
}

function buildDraftReportText(
  title: string,
  channelName: string,
  requestedOutcome: ManualReportRequestedOutcome,
  workflowMode: 'report' | 'verify-transparent',
  selectedTags: ManualReviewTag[],
  suggestedOutcomeReason: string | null,
  issues: Array<{ label: string; comment: string }>,
): string {
  const openingLine =
    workflowMode === 'verify-transparent'
      ? `Transparency verification: this appears to be honest ${selectedTags.join(', ') || 'content'}.`
      : requestedOutcome === 'remove'
        ? 'Requested action: Please remove this content because the presentation appears materially misleading.'
        : 'Requested action: Please moderate this content so the presentation becomes consistent and non-misleading.';
  const lines = [
    openingLine,
    `Video: "${title}"`,
    `Channel: ${channelName}`,
    ...(selectedTags.length > 0 ? [`Selected tags: ${selectedTags.join(', ')}`] : []),
    ...(suggestedOutcomeReason ? [`TruthLens rationale: ${suggestedOutcomeReason}`] : []),
    '',
    workflowMode === 'verify-transparent'
      ? 'Transparency notes:'
      : 'Requested review for potentially misleading presentation in these areas:',
    ...issues.map((issue) => `- ${issue.label}: ${issue.comment}`),
  ];

  return lines.join('\n').trim();
}

function requestedOutcomeLabel(value: ManualReportRequestedOutcome): string {
  return value === 'remove' ? 'Remove' : 'Moderate';
}

function shouldUsePageReportFallback(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("did not return a suitable 'spam or misleading' report category") ||
    normalized.includes("could not verify direct youtube reporting capability") ||
    normalized.includes("youtube oauth has not been connected yet") ||
    normalized.includes("youtube oauth is not configured") ||
    normalized.includes("youtube oauth token is missing") ||
    normalized.includes("youtube report submission failed: 409") ||
    normalized.includes("youtube report submission failed: 503")
  );
}

function selectedTagsFromSuggestions(
  suggestions: ManualReviewTagSelection[],
): SelectedTagState {
  const nextState = { ...DEFAULT_SELECTED_TAGS };
  suggestions.forEach((selection) => {
    nextState[selection.tag] = selection.selected;
  });
  return nextState;
}

function selectedTagList(selectedTags: SelectedTagState): ManualReviewTag[] {
  return TAG_OPTIONS.filter(({ tag }) => selectedTags[tag]).map(({ tag }) => tag);
}

function isCollectionBatch(scope: ManualReviewCollectionScope | null): boolean {
  return Boolean(scope && scope.scope_type !== 'single' && scope.member_items.length > 1);
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
  const [selectedTags, setSelectedTags] = useState<SelectedTagState>(DEFAULT_SELECTED_TAGS);
  const [suggestedTags, setSuggestedTags] = useState<ManualReviewTagSelection[]>([]);
  const [originalComments, setOriginalComments] = useState<Partial<IssueCommentState>>({});
  const [optimizeChoice, setOptimizeChoice] = useState<'yes' | 'no'>('no');
  const [requestedOutcome, setRequestedOutcome] =
    useState<ManualReportRequestedOutcome>('moderate');
  const [suggestedOutcomeReason, setSuggestedOutcomeReason] = useState<string | null>(null);
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
  const [collectionConfirmed, setCollectionConfirmed] = useState(false);
  const [reviewEvidence, setReviewEvidence] = useState<ReviewEvidence>(EMPTY_REVIEW_EVIDENCE);
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
    setSelectedTags(
      manualReportTarget?.workflowMode === 'verify-transparent'
        ? { ...DEFAULT_SELECTED_TAGS, Unknown: true }
        : { ...DEFAULT_SELECTED_TAGS, Clickbait: true },
    );
    setSuggestedTags([]);
    setOriginalComments({});
    setOptimizeChoice('no');
    setRequestedOutcome('moderate');
    setSuggestedOutcomeReason(null);
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
    setCollectionConfirmed(false);
    setReviewEvidence(reviewEvidenceFromTarget(manualReportTarget));
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
                ? status.direct_reporting_supported
                  ? `YouTube direct reporting is connected${status.channel_name ? ` as ${status.channel_name}` : ''}.`
                : `${status.channel_name ? `Connected as ${status.channel_name}. ` : ''}${status.direct_reporting_detail ?? 'TruthLens will use YouTube’s in-page report flow on the current page.'}`
              : status.configured
                ? 'YouTube reporting is configured but still needs account authorization.'
                : 'This TruthLens deployment is not configured for direct YouTube reporting yet.',
            status.connected && status.direct_reporting_supported ? 'success' : 'info',
          );
        })
        .catch(() => {
          if (cancelled) {
            return;
          }
          setErrorMessage('Could not load YouTube reporting status from the current TruthLens API.');
          appendStatusLine('Could not load YouTube reporting status from the current TruthLens API.', 'error');
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
      const transcriptAvailable =
        typeof enrichedMetadata.transcriptAvailable === 'boolean'
          ? enrichedMetadata.transcriptAvailable
          : Boolean(transcriptExcerpt);
      const nextReviewEvidence = {
        descriptionSnapshot,
        transcriptExcerpt,
        transcriptAvailable,
        channelUrl: enrichedMetadata.channelUrl ?? manualReportTarget.channelUrl,
        channelContext: enrichedMetadata.channelContext,
      } satisfies ReviewEvidence;
      if (!cancelled) {
        setReviewEvidence(nextReviewEvidence);
      }
      appendStatusLine('Drafting initial comments with Gemini…');

      return suggestManualReportComments({
        workflow_mode: manualReportTarget.workflowMode,
        target_url: manualReportTarget.linkUrl,
        thumbnail_ref: manualReportTarget.thumbnailRef,
        title_snapshot: manualReportTarget.title,
        channel_name: manualReportTarget.channelName,
        channel_url: nextReviewEvidence.channelUrl,
        channel_context: nextReviewEvidence.channelContext,
        description_snapshot: nextReviewEvidence.descriptionSnapshot,
        transcript_excerpt:
          nextReviewEvidence.transcriptAvailable === true &&
          nextReviewEvidence.transcriptExcerpt &&
          nextReviewEvidence.transcriptExcerpt !== nextReviewEvidence.descriptionSnapshot
            ? nextReviewEvidence.transcriptExcerpt
            : null,
        transcript_available: nextReviewEvidence.transcriptAvailable,
        explanation_summary: manualReportTarget.score?.explanation_summary ?? null,
        reasons: manualReportTarget.score?.reasons ?? [],
        content_class: manualReportTarget.score?.content_class ?? 'unknown',
        content_class_confidence: manualReportTarget.score?.content_class_confidence ?? 0,
        collection_scope: manualReportTarget.collectionScope,
        bias_profile: manualReportTarget.score?.bias_profile ?? {
          metrics: {},
          positive_biases: [],
          negative_biases: [],
          guardrail_applied: null,
        },
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
        setSelectedTags(selectedTagsFromSuggestions(draft.suggested_tags));
        setSuggestedTags(draft.suggested_tags);
        setRequestedOutcome(draft.suggested_outcome);
        setSuggestedOutcomeReason(draft.suggested_outcome_reason);
        setDraftModel(draft.suggestion_model);
        appendStatusLine(
          draft.suggestion_model.startsWith('truthlens-heuristic-')
            ? 'Initial TruthLens draft suggestions are ready using local heuristics.'
            : 'Initial draft suggestions are ready for review.',
          'success',
        );
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
    }, 2400);

    return () => {
      window.clearTimeout(closeTimer);
    };
  }, [closeManualReport, manualReportTarget, submissionCompleted]);

  const transcriptIssueVisible =
    reviewEvidence.transcriptAvailable === true &&
    Boolean(reviewEvidence.transcriptExcerpt?.trim());
  const visibleIssueOptions = ISSUE_OPTIONS.filter(({ issueType }) => {
    return issueType !== 'transcript' || transcriptIssueVisible;
  });
  const activeIssues = visibleIssueOptions.filter(({ issueType }) => selectedIssues[issueType]).map(
    ({ issueType, label }) => ({
      issueType,
      label,
      comment: comments[issueType].trim(),
    }),
  );
  const activeTags = selectedTagList(selectedTags);
  const missingComments = activeIssues.some((issue) => issue.comment.length === 0);
  const collectionScope = manualReportTarget?.collectionScope ?? null;
  const collectionBatch = isCollectionBatch(collectionScope);
  const batchTargets =
    collectionBatch && collectionConfirmed && collectionScope
      ? collectionScope.member_items
      : [];
  const hasDirectReportTarget =
    manualReportTarget?.workflowMode === 'verify-transparent'
      ? true
      : collectionBatch
        ? batchTargets.some((member) => Boolean(member.link_url))
        : Boolean(manualReportTarget?.linkUrl);
  const canUseDirectYouTubeReporting =
    youtubeAuthStatus?.connected === true && youtubeAuthStatus.direct_reporting_supported;
  const canUseSingleItemPageFallback =
    manualReportTarget?.workflowMode !== 'verify-transparent' &&
    !collectionBatch &&
    Boolean(manualReportTarget?.linkUrl);
  const previewText = manualReportTarget
    ? optimizationApplied && optimizedReportText
      ? optimizedReportText
      : buildDraftReportText(
          manualReportTarget.title,
          manualReportTarget.channelName,
          requestedOutcome,
          manualReportTarget.workflowMode,
          activeTags,
          suggestedOutcomeReason,
          activeIssues,
        )
    : '';
  const canSubmit =
    manualReportTarget !== null &&
    activeIssues.length > 0 &&
    activeTags.length > 0 &&
    !missingComments &&
    (!manualReportTarget || optimizeChoice === 'no' || optimizationApplied) &&
    (!collectionBatch || collectionConfirmed) &&
    (manualReportTarget?.workflowMode === 'verify-transparent' ||
      (collectionBatch ? true : Boolean(canUseSingleItemPageFallback || hasDirectReportTarget)));

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
      const transcriptExcerpt =
        reviewEvidence.transcriptAvailable === true ? reviewEvidence.transcriptExcerpt : null;
      const response = await optimizeManualReportComments({
        workflow_mode: manualReportTarget.workflowMode,
      target_url: manualReportTarget.linkUrl,
      title_snapshot: manualReportTarget.title,
      channel_name: manualReportTarget.channelName,
      transcript_excerpt: transcriptExcerpt,
      requested_outcome: requestedOutcome,
      selected_tags: activeTags,
      collection_scope:
        collectionBatch && collectionScope
          ? {
              ...collectionScope,
              apply_to_all: collectionConfirmed,
              trigger_origin: collectionConfirmed ? 'collection-preview' : 'single-item',
            }
          : null,
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
        'Rapporten kr\u00e6ver mindst \u00e9n udfyldt fejlbeskrivelse og en tilg\u00e6ngelig YouTube-reportvej.',
      );
      return;
    }
    if (!hasDirectReportTarget) {
      setErrorMessage('TruthLens could not determine a YouTube video URL for this report.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setSubmissionCompleted(false);
    const effectiveCollectionScope =
      collectionBatch && collectionScope
        ? {
            ...collectionScope,
            apply_to_all: true,
            trigger_origin: 'collection-preview' as const,
          }
        : collectionScope;
    const reviewUserAction =
      manualReportTarget.workflowMode === 'verify-transparent'
        ? 'confirm-transparent'
        : 'confirm-report';
    const collectionSummaryAction = `${reviewUserAction}-collection`;
    const manualReportIssues = activeIssues.map((issue) => ({
      issue_type: issue.issueType,
      comment: comments[issue.issueType].trim(),
      original_comment: originalComments[issue.issueType] ?? null,
    }));
    const reviewTargets =
      collectionBatch && collectionConfirmed && effectiveCollectionScope
        ? effectiveCollectionScope.member_items
        : [
            {
              item_id: manualReportTarget.itemId,
              title_snapshot: manualReportTarget.title,
              channel_name: manualReportTarget.channelName,
              link_url: manualReportTarget.linkUrl,
              thumbnail_ref: manualReportTarget.thumbnailRef,
              resolved: Boolean(manualReportTarget.linkUrl),
            },
          ];
    const afterReportScore =
      manualReportTarget.workflowMode === 'report'
        ? riskScoreAfterReportFeedback(
            manualReportTarget.score,
            requestedOutcome,
            manualReportTarget.channelReportCount,
          )
        : manualReportTarget.score?.risk_score ?? null;

    const buildManualReport = (target: {
      item_id: string;
      title_snapshot?: string | null;
      link_url?: string | null;
      thumbnail_ref?: string | null;
    }) => ({
      workflow_mode: manualReportTarget.workflowMode,
      target_url: target.link_url ?? null,
      thumbnail_ref: target.thumbnail_ref ?? manualReportTarget.thumbnailRef,
      title_snapshot: target.title_snapshot ?? manualReportTarget.title,
      transcript_excerpt:
        reviewEvidence.transcriptAvailable === true ? reviewEvidence.transcriptExcerpt : null,
      issues: manualReportIssues,
      requested_outcome: requestedOutcome,
      suggested_outcome_reason: suggestedOutcomeReason,
      selected_tags: activeTags,
      suggested_tags: suggestedTags,
      collection_scope: effectiveCollectionScope,
      optimize_requested: optimizeChoice === 'yes',
      optimize_applied: optimizationApplied,
      optimization_model: optimizationModel,
      report_text: previewText,
    } as const);

    try {
      let successText: string;
      if (manualReportTarget.workflowMode === 'verify-transparent') {
        appendStatusLine(
          collectionBatch && collectionConfirmed
            ? `Saving a positive transparency verification for ${reviewTargets.length} collection items…`
            : 'Saving a positive transparency verification to TruthLens…',
        );
        successText = collectionBatch && collectionConfirmed
          ? `Den positive transparens-verifikation blev gemt lokalt for ${reviewTargets.length} items i samlingen.`
          : 'Den positive transparens-verifikation blev gemt lokalt som TruthLens-feedback.';
      } else if (collectionBatch && collectionConfirmed && effectiveCollectionScope) {
        const resolvableTargets = reviewTargets.filter((target) => Boolean(target.link_url));
        let reportedCount = 0;
        let failedCount = 0;
        const skippedCount = reviewTargets.length - resolvableTargets.length;
        if (!canUseDirectYouTubeReporting) {
          appendStatusLine(
            youtubeAuthStatus?.direct_reporting_detail ??
              'Direct YouTube API reporting is unavailable for this account, so TruthLens will only store internal batch review provenance for this collection.',
          );
          successText = `TruthLens stored the batch review for this ${effectiveCollectionScope.scope_type} inside TruthLens only. It skipped ${reviewTargets.length} external collection reports because direct YouTube API reporting is unavailable for this account.`;
        } else {
          appendStatusLine(
            `Submitting direct YouTube reports for ${resolvableTargets.length} item(s) in this ${effectiveCollectionScope.scope_type}…`,
          );
          for (const target of reviewTargets) {
            if (!target.link_url) {
              appendStatusLine(
                `Skipped one collection item because TruthLens could not resolve a watch URL.`,
              );
              continue;
            }
            try {
              await submitYouTubeReport({
                target_url: target.link_url,
                report_text: previewText,
                issue_types: activeIssues.map((issue) => issue.issueType),
              });
              reportedCount += 1;
              appendStatusLine(
                `Direct YouTube report accepted for "${target.title_snapshot ?? target.item_id}".`,
                'success',
              );
            } catch (error) {
              failedCount += 1;
              appendStatusLine(
                error instanceof Error
                  ? `Could not report "${target.title_snapshot ?? target.item_id}": ${error.message}`
                  : `Could not report "${target.title_snapshot ?? target.item_id}".`,
                'error',
              );
            }
          }
          successText =
            reportedCount > 0
              ? `TruthLens reported ${reportedCount} collection item(s) directly to YouTube, skipped ${skippedCount}, and saw ${failedCount} API failure(s). Internal batch review provenance was still stored for the whole collection.`
              : `TruthLens could not submit any external YouTube reports for this collection. It skipped ${skippedCount} unresolved item(s), saw ${failedCount} API failure(s), and stored the batch review only inside TruthLens.`;
        }
      } else {
        const issueTypes = activeIssues.map((issue) => issue.issueType);
        if (!canUseDirectYouTubeReporting) {
          appendStatusLine(
            youtubeAuthStatus?.direct_reporting_detail ??
              'Direct YouTube API reporting is unavailable, so TruthLens is using YouTube’s in-page report flow on the current page…',
          );
          const youtubePageReport = await submitYouTubePageReport(manualReportTarget, issueTypes);
          successText = youtubePageReport.secondary_reason_label
            ? `Rapporten blev sendt via YouTubes indbyggede report-flow under "${youtubePageReport.reason_label}" / "${youtubePageReport.secondary_reason_label}"`
            : `Rapporten blev sendt via YouTubes indbyggede report-flow under "${youtubePageReport.reason_label}"`;
          appendStatusLine(
            'The in-page YouTube report flow completed on the current page.',
            'success',
          );
        } else {
          appendStatusLine('Submitting the report to YouTube…');
          try {
            const youtubeReport = await submitYouTubeReport({
              target_url: manualReportTarget.linkUrl!,
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
              'Direct YouTube API reporting was unavailable, so TruthLens is using YouTube’s in-page report flow on the current page…',
            );
            const youtubePageReport = await submitYouTubePageReport(manualReportTarget, issueTypes);
            successText = youtubePageReport.secondary_reason_label
              ? `Rapporten blev sendt via YouTubes indbyggede report-flow under "${youtubePageReport.reason_label}" / "${youtubePageReport.secondary_reason_label}"`
              : `Rapporten blev sendt via YouTubes indbyggede report-flow under "${youtubePageReport.reason_label}"`;
            appendStatusLine(
              'The in-page YouTube report flow completed on the current page.',
              'success',
            );
          }
        }
      }

      if (collectionBatch && collectionConfirmed) {
        await sendFeedbackEvent(
          createFeedbackPayload(
            manualReportTarget.itemId,
            manualReportTarget.channelName,
            manualReportTarget.score?.recommended_action ?? 'none',
            manualReportTarget.score?.risk_score ?? null,
            manualReportTarget.score?.explanation_id ?? null,
            buildManualReport({
              item_id: manualReportTarget.itemId,
              title_snapshot: manualReportTarget.title,
              link_url: manualReportTarget.linkUrl,
              thumbnail_ref: manualReportTarget.thumbnailRef,
            }),
            collectionSummaryAction,
            manualReportTarget.score?.artifact_provenance ?? null,
            afterReportScore,
          ),
        );
      }

      for (const target of reviewTargets) {
        await sendFeedbackEvent(
          createFeedbackPayload(
            target.item_id,
            target.channel_name ?? manualReportTarget.channelName,
            manualReportTarget.score?.recommended_action ?? 'none',
            manualReportTarget.score?.risk_score ?? null,
            manualReportTarget.score?.explanation_id ?? null,
            buildManualReport(target),
            reviewUserAction,
            manualReportTarget.score?.artifact_provenance ?? null,
            afterReportScore,
          ),
        );
      }
      dispatchManualReviewSubmitted({
        workflowMode: manualReportTarget.workflowMode,
        userAction: reviewUserAction,
        requestedOutcome,
        targets: reviewTargets.map((target) => ({
          itemId: target.item_id,
          channelName: target.channel_name ?? manualReportTarget.channelName,
          linkUrl: target.link_url ?? null,
          thumbnailRef: target.thumbnail_ref ?? manualReportTarget.thumbnailRef,
        })),
      });
      appendStatusLine(
        collectionBatch && collectionConfirmed
          ? `TruthLens feedback was stored locally for ${reviewTargets.length} collection item(s).`
          : 'TruthLens feedback was stored locally.',
        'success',
      );
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
    const authUrl = youtubeAuthStatus?.auth_url ?? buildTruthLensApiUrl('/youtube/auth/start');
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
                ? 'Mark what appears transparent and consistent. Choose the honest content tag TruthLens suggests, then adjust any packaging notes that need correction.'
                : 'Mark what looks wrong. TruthLens will preselect Clickbait, but you can override the classification tag before submitting the review.'}
            </p>

            {manualReportTarget.score ? (
              <div className="truthlens-score-summary">
                <p className="truthlens-preview-label">TruthLens context</p>
                <div className="truthlens-score-summary-grid">
                  <p className="truthlens-score-summary-item">
                    Class {manualReportTarget.score.content_class} with confidence{' '}
                    {manualReportTarget.score.content_class_confidence.toFixed(2)}.
                  </p>
                  <p className="truthlens-score-summary-item">
                    Current action {manualReportTarget.score.recommended_action} at risk{' '}
                    {manualReportTarget.score.risk_score.toFixed(2)}.
                  </p>
                  {manualReportTarget.score.bias_profile.guardrail_applied ? (
                    <p className="truthlens-score-summary-item">
                      Guardrail {manualReportTarget.score.bias_profile.guardrail_applied}.
                    </p>
                  ) : null}
                  {manualReportTarget.score.bias_profile.positive_biases.length > 0 ? (
                    <p className="truthlens-score-summary-item">
                      Preserved bias{' '}
                      {manualReportTarget.score.bias_profile.positive_biases.join(', ')}.
                    </p>
                  ) : null}
                  {manualReportTarget.score.bias_profile.negative_biases.length > 0 ? (
                    <p className="truthlens-score-summary-item">
                      Negative bias{' '}
                      {manualReportTarget.score.bias_profile.negative_biases.join(', ')}.
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {collectionBatch && collectionScope ? (
              <div className="truthlens-score-summary">
                <p className="truthlens-preview-label">Collection scope</p>
                <div className="truthlens-score-summary-grid">
                  <p className="truthlens-score-summary-item">
                    TruthLens detected a {collectionScope.scope_type} with{' '}
                    {collectionScope.member_items.length} visible member(s).
                  </p>
                  <p className="truthlens-score-summary-item">
                    Resolved watch URLs: {collectionScope.resolved_member_count}. Unresolved items:{' '}
                    {collectionScope.unresolved_member_count}.
                  </p>
                  <p className="truthlens-score-summary-item">
                    Preview titles:{' '}
                    {collectionScope.member_items
                      .slice(0, 4)
                      .map((member) => member.title_snapshot ?? member.item_id)
                      .join(' | ')}
                  </p>
                </div>
                <label className="truthlens-collection-confirm">
                  <input
                    checked={collectionConfirmed}
                    onChange={(event) => {
                      setCollectionConfirmed(event.target.checked);
                      setErrorMessage(null);
                      setSuccessMessage(null);
                    }}
                    type="checkbox"
                  />
                  <span>
                    Apply this {manualReportTarget.workflowMode === 'verify-transparent' ? 'verification' : 'report'}
                    {' '}to all {collectionScope.member_items.length} visible items in the same{' '}
                    {collectionScope.scope_type}.
                  </span>
                </label>
              </div>
            ) : null}

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
              {TAG_OPTIONS.map(({ tag, label }) => {
                const suggestion = suggestedTags.find((entry) => entry.tag === tag) ?? null;
                return (
                  <label className="truthlens-issue-card truthlens-tag-card" key={tag}>
                    <span className="truthlens-issue-toggle">
                      <input
                        checked={selectedTags[tag]}
                        onChange={(event) => {
                          setSelectedTags((state) => ({
                            ...state,
                            [tag]: event.target.checked,
                          }));
                          setErrorMessage(null);
                          setSuccessMessage(null);
                        }}
                        type="checkbox"
                      />
                      <span>{label}</span>
                    </span>
                    {suggestion?.rationale ? (
                      <p className="truthlens-tag-rationale">
                        {suggestion.rationale}
                        {typeof suggestion.confidence === 'number'
                          ? ` (${Math.round(suggestion.confidence * 100)}%)`
                          : ''}
                      </p>
                    ) : null}
                  </label>
                );
              })}
            </div>

            <div className="truthlens-report-grid">
              {visibleIssueOptions.map(({ issueType, label }) => (
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
                      placeholder={
                        manualReportTarget.workflowMode === 'verify-transparent'
                          ? `Describe briefly why the ${label.toLowerCase()} looks honest or consistent.`
                          : `Describe the ${label.toLowerCase()} issue briefly.`
                      }
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

            {suggestedOutcomeReason ? (
              <p className="truthlens-preview-meta">TruthLens recommendation: {suggestedOutcomeReason}</p>
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
                  <p className="truthlens-preview-empty">Checking YouTube reporting availability...</p>
                ) : youtubeAuthStatus?.connected ? (
                  youtubeAuthStatus.direct_reporting_supported ? (
                    <p className="truthlens-platform-message">
                      Direct reporting is connected
                      {youtubeAuthStatus.channel_name ? ` as ${youtubeAuthStatus.channel_name}` : ''}. If
                      the YouTube API later stops exposing a misleading category for this account,
                      TruthLens
                      {collectionBatch
                        ? ' will keep unresolved collection members as internal TruthLens review state only.'
                        : ' will fall back to YouTube’s in-page report flow on the current page.'}
                    </p>
                  ) : (
                    <p className="truthlens-platform-message">
                      {youtubeAuthStatus.channel_name
                        ? `Connected as ${youtubeAuthStatus.channel_name}. `
                        : ''}
                      {youtubeAuthStatus.direct_reporting_detail ??
                        'This account cannot use direct YouTube API reporting for misleading reports right now.'}{' '}
                      {collectionBatch
                        ? 'TruthLens will store collection batch review provenance internally instead of claiming an external batch report.'
                        : 'TruthLens will use YouTube’s in-page report flow on the current page instead of the direct API.'}
                    </p>
                  )
                ) : youtubeAuthStatus?.configured ? (
                  <>
                    <p className="truthlens-platform-message">
                      Connect your YouTube account once to let TruthLens use direct API reporting
                      when the account supports it. Single-item reports can still use TruthLens&apos;s
                      in-page YouTube fallback on the current page.
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
                    <code>TRUTHLENS_YOUTUBE_CLIENT_SECRET</code>, and either{' '}
                    <code>TRUTHLENS_PUBLIC_API_BASE</code> or{' '}
                    <code>TRUTHLENS_YOUTUBE_REDIRECT_URI</code>, then set{' '}
                    <code>TRUTHLENS_YOUTUBE_DIRECT_REPORTING_ENABLED=true</code> if you want this
                    hosted deployment to expose direct OAuth/report-submit. Until then, TruthLens
                    falls back to YouTube&apos;s in-page flow.
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
                    {suggestedOutcomeReason ? (
                      <p className="truthlens-preview-channel">{suggestedOutcomeReason}</p>
                    ) : null}
                  </div>

                  <div className="truthlens-preview-section">
                    <p className="truthlens-preview-section-title">Selected tags</p>
                    {activeTags.length > 0 ? (
                      <p className="truthlens-preview-channel">{activeTags.join(', ')}</p>
                    ) : (
                      <p className="truthlens-preview-empty">
                        Choose at least one classification tag before submitting.
                      </p>
                    )}
                  </div>

                  <div className="truthlens-preview-section">
                    <p className="truthlens-preview-section-title">Scope</p>
                    <p className="truthlens-preview-channel">
                      {collectionBatch && collectionScope
                        ? collectionConfirmed
                          ? `Apply to all ${collectionScope.member_items.length} visible items in the same ${collectionScope.scope_type}.`
                          : `Collection detected (${collectionScope.member_items.length} visible items). Confirmation is required before batch submit.`
                        : 'Single item'}
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
                <p className="truthlens-preview-meta">Drafting initial suggestions with TruthLens...</p>
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
                    ? collectionBatch && collectionConfirmed
                      ? `Verify ${batchTargets.length} items`
                      : 'Verify'
                    : collectionBatch && collectionConfirmed
                      ? `Report ${batchTargets.length} items`
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
