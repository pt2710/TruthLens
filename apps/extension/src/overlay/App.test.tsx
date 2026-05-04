// @vitest-environment jsdom
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { scoreResultSchema, type ManualReportSuggestionResponse } from '@truthlens/shared-schemas';

const apiMocks = vi.hoisted(() => ({
  fetchYouTubeAuthStatus: vi.fn(),
  optimizeManualReportComments: vi.fn(),
  sendFeedbackEvent: vi.fn(),
  suggestManualReportComments: vi.fn(),
  submitYouTubeReport: vi.fn(),
}));

const metadataMocks = vi.hoisted(() => ({
  fetchYouTubeWatchMetadata: vi.fn(),
}));

const pageReportingMocks = vi.hoisted(() => ({
  submitYouTubePageReport: vi.fn(),
}));

vi.mock('../lib/api', () => apiMocks);
vi.mock('../lib/youtubeWatchMetadata', () => metadataMocks);
vi.mock('../lib/youtubePageReporting', () => pageReportingMocks);

import { App } from './App';
import { useOverlayStore, type ManualReportTarget } from './store';

function makeScore() {
  return scoreResultSchema.parse({
    risk_score: 0.71,
    confidence: 0.83,
    uncertainty: 0.17,
    content_class: 'music',
    content_class_confidence: 0.91,
    bias_profile: {
      metrics: {},
      positive_biases: ['stylistic-divergence-tolerance'],
      negative_biases: [],
      guardrail_applied: 'music-context-dampens-crossmodal-rigidity',
    },
    recommended_action: 'blur',
    reasons: ['The packaging is review-worthy.'],
    explanation_id: 'exp-overlay-test',
    explanation_summary: 'TruthLens has review context for this item.',
    evidence: [],
  });
}

function makeSuggestion(
  workflowMode: 'report' | 'verify-transparent',
  transcriptAvailable = false,
): ManualReportSuggestionResponse {
  return {
    issues: [
      {
        issue_type: 'title',
        suggested: true,
        comment:
          workflowMode === 'verify-transparent'
            ? 'The title accurately represents the content and should stay as-is.'
            : 'The title overpromises relative to the visible evidence.',
      },
      { issue_type: 'thumbnail', suggested: false, comment: '' },
      { issue_type: 'description', suggested: false, comment: '' },
      {
        issue_type: 'transcript',
        suggested: transcriptAvailable,
        comment: transcriptAvailable
          ? 'The transcript context should be reviewed alongside the packaging.'
          : '',
      },
      { issue_type: 'channel', suggested: false, comment: '' },
      {
        issue_type: 'other',
        suggested: workflowMode === 'report',
        comment:
          workflowMode === 'report'
            ? 'The overall packaging leans on mismatch and clickbait framing.'
            : '',
      },
    ],
    suggested_outcome: workflowMode === 'report' ? 'moderate' : 'remove',
    suggested_outcome_reason:
      workflowMode === 'report'
        ? 'TruthLens recommends Moderate because the packaging appears misleading.'
        : 'TruthLens recommends this honest-content tag because the metadata is consistent.',
    suggested_tags:
      workflowMode === 'report'
        ? [
            {
              tag: 'Clickbait',
              selected: true,
              confidence: 0.94,
              rationale: 'Report mode defaults to Clickbait.',
            },
            {
              tag: 'News',
              selected: false,
              confidence: 0.22,
              rationale: 'News context is weaker than the deceptive packaging signal.',
            },
          ]
        : [
            {
              tag: 'Music',
              selected: true,
              confidence: 0.9,
              rationale: 'TruthLens sees a consistent music presentation.',
            },
            {
              tag: 'Documentary',
              selected: false,
              confidence: 0.18,
              rationale: 'Documentary cues are weaker than the music cues.',
            },
          ],
    suggestion_model: 'truthlens-heuristic-fallback-v1',
  };
}

function makeTarget(
  workflowMode: 'report' | 'verify-transparent',
  collection = false,
): ManualReportTarget {
  const collectionScope = collection
    ? {
        scope_type: 'playlist' as const,
        scope_id: 'PL-test-playlist',
        collection_title: 'Test playlist',
        source_link_url: 'https://www.youtube.com/watch?v=item-1&list=PL-test-playlist',
        trigger_origin: 'single-item' as const,
        apply_to_all: false,
        resolved_member_count: 2,
        unresolved_member_count: 0,
        member_items: [
          {
            item_id: 'item-1',
            title_snapshot: 'Track 1',
            link_url: 'https://www.youtube.com/watch?v=item-1&list=PL-test-playlist',
            thumbnail_ref: 'https://img.youtube.com/vi/item-1/default.jpg',
            resolved: true,
          },
          {
            item_id: 'item-2',
            title_snapshot: 'Track 2',
            link_url: 'https://www.youtube.com/watch?v=item-2&list=PL-test-playlist',
            thumbnail_ref: 'https://img.youtube.com/vi/item-2/default.jpg',
            resolved: true,
          },
        ],
      }
    : null;

  return {
    itemId: 'item-1',
    workflowMode,
    title: workflowMode === 'report' ? 'Breaking story' : 'Moonlight Echoes (Official Audio)',
    channelName: workflowMode === 'report' ? 'Signal Watch' : 'Aurora Records',
    channelUrl: 'https://www.youtube.com/@aurorarecords',
    linkUrl: 'https://www.youtube.com/watch?v=item-1',
    thumbnailRef: 'https://img.youtube.com/vi/item-1/default.jpg',
    descriptionSnapshot: 'Description snapshot',
    transcriptExcerpt: null,
    collectionScope,
    channelReportCount: 2,
    score: makeScore(),
  };
}

function resetStore() {
  useOverlayStore.setState({
    itemCount: 0,
    flaggedCount: 0,
    lastScore: null,
    scoresByItemId: {},
    manualReportTarget: null,
    recordScore: useOverlayStore.getState().recordScore,
    openManualReport: useOverlayStore.getState().openManualReport,
    closeManualReport: useOverlayStore.getState().closeManualReport,
  });
}

async function flushUi() {
  for (let index = 0; index < 3; index += 1) {
    await Promise.resolve();
    await new Promise((resolve) => window.setTimeout(resolve, 0));
  }
}

function getTagCheckbox(label: string): HTMLInputElement {
  const card = Array.from(document.querySelectorAll<HTMLLabelElement>('.truthlens-tag-card')).find(
    (entry) => entry.textContent?.includes(label),
  );
  if (!card) {
    throw new Error(`Could not find tag card for ${label}`);
  }
  const input = card.querySelector<HTMLInputElement>('input[type="checkbox"]');
  if (!input) {
    throw new Error(`Could not find checkbox for ${label}`);
  }
  return input;
}

function getIssueCard(label: string): HTMLLabelElement {
  const card = Array.from(document.querySelectorAll<HTMLLabelElement>('.truthlens-issue-card'))
    .filter((entry) => !entry.classList.contains('truthlens-tag-card'))
    .find((entry) => entry.textContent?.includes(label));
  if (!card) {
    throw new Error(`Could not find issue card for ${label}`);
  }
  return card;
}

describe('manual review overlay', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    resetStore();
    apiMocks.fetchYouTubeAuthStatus.mockResolvedValue({
      configured: true,
      connected: true,
      auth_url: null,
      channel_name: 'TruthLens Test Channel',
      direct_reporting_supported: true,
      direct_reporting_detail: 'Direct YouTube API reporting is available for this account.',
    });
    apiMocks.optimizeManualReportComments.mockResolvedValue({
      issues: [],
      optimization_model: 'truthlens-heuristic-optimizer-v1',
      report_text: 'Optimized preview text',
      selected_tags: [],
    });
    apiMocks.sendFeedbackEvent.mockResolvedValue({
      status: 'remote',
      transport: 'content-fetch',
      queued_count: 0,
      flushed_count: 0,
    });
    apiMocks.suggestManualReportComments.mockImplementation(
      async (payload: {
        workflow_mode: 'report' | 'verify-transparent';
        transcript_available?: boolean | null;
      }) => makeSuggestion(payload.workflow_mode, payload.transcript_available === true),
    );
    apiMocks.submitYouTubeReport.mockResolvedValue({
      reason_id: 'reason',
      reason_label: 'Spam or misleading',
      secondary_reason_id: 'secondary',
      secondary_reason_label: 'Scam or fraud',
      submitted_at: '2026-04-10T00:00:00Z',
    });
    pageReportingMocks.submitYouTubePageReport.mockResolvedValue({
      status: 'reported',
      reason_label: 'Spam or misleading',
      secondary_reason_label: 'Misleading metadata',
    });
    metadataMocks.fetchYouTubeWatchMetadata.mockResolvedValue({
      descriptionSnapshot: null,
      transcriptExcerpt: null,
      transcriptAvailable: false,
      channelUrl: null,
      channelContext: null,
    });
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    root.render(<App />);
    await flushUi();
  });

  afterEach(async () => {
    vi.useRealTimers();
    root.unmount();
    container.remove();
    resetStore();
    vi.clearAllMocks();
  });

  it('keeps report mode focused on Clickbait tagging', async () => {
    useOverlayStore.getState().openManualReport(makeTarget('report'));
    await flushUi();

    expect(getTagCheckbox('Clickbait').checked).toBe(true);
    expect(getTagCheckbox('News').checked).toBe(false);
    expect(document.body.textContent).toContain('TruthLens recommends Moderate because the packaging appears misleading.');
    expect(document.body.textContent).toContain('Initial TruthLens draft suggestions are ready using local heuristics.');
  });

  it('hides transcript review when watch transcript evidence is unavailable and submits null transcript context', async () => {
    useOverlayStore.getState().openManualReport(makeTarget('report'));
    await flushUi();

    const issueTexts = Array.from(document.querySelectorAll('.truthlens-issue-card')).map((node) =>
      node.textContent?.trim() ?? '',
    );
    expect(issueTexts.some((text) => text.includes('Transcript'))).toBe(false);

    const optimizeYes = document.querySelectorAll<HTMLInputElement>(
      'input[name="truthlens-optimize-choice"]',
    )[0];
    if (!optimizeYes) {
      throw new Error('Missing optimize choice');
    }
    optimizeYes.click();
    await flushUi();

    const optimizeButton = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.truthlens-secondary-button'),
    ).find((button) => button.textContent?.includes('Optimize comments'));
    const submitButton = document.querySelector<HTMLButtonElement>('.truthlens-primary-button');
    if (!optimizeButton || !submitButton) {
      throw new Error('Missing report buttons');
    }

    optimizeButton.click();
    await flushUi();
    submitButton.click();
    await flushUi();

    expect(apiMocks.optimizeManualReportComments).toHaveBeenCalledTimes(1);
    expect(apiMocks.optimizeManualReportComments.mock.calls[0][0].transcript_excerpt).toBeNull();
    expect(apiMocks.sendFeedbackEvent).toHaveBeenCalledTimes(1);
    expect(apiMocks.sendFeedbackEvent.mock.calls[0][0].manual_report.transcript_excerpt).toBeNull();
    expect(apiMocks.sendFeedbackEvent.mock.calls[0][0].after_score).toBeGreaterThan(
      apiMocks.sendFeedbackEvent.mock.calls[0][0].before_score,
    );
  });

  it('shows transcript review only when fetched watch metadata provides transcript evidence', async () => {
    metadataMocks.fetchYouTubeWatchMetadata.mockResolvedValue({
      descriptionSnapshot: 'Fetched description snapshot',
      transcriptExcerpt: 'Fetched transcript evidence from captions.',
      transcriptAvailable: true,
      channelUrl: 'https://www.youtube.com/@signalwatch',
      channelContext: 'Recent public channel titles: "Weekly lab update"',
    });

    useOverlayStore.getState().openManualReport(makeTarget('report'));
    await flushUi();

    const issueTexts = Array.from(document.querySelectorAll('.truthlens-issue-card')).map((node) =>
      node.textContent?.trim() ?? '',
    );
    expect(issueTexts.some((text) => text.includes('Transcript'))).toBe(true);

    const optimizeYes = document.querySelectorAll<HTMLInputElement>(
      'input[name="truthlens-optimize-choice"]',
    )[0];
    if (!optimizeYes) {
      throw new Error('Missing optimize choice');
    }
    optimizeYes.click();
    await flushUi();

    const optimizeButton = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.truthlens-secondary-button'),
    ).find((button) => button.textContent?.includes('Optimize comments'));
    const submitButton = document.querySelector<HTMLButtonElement>('.truthlens-primary-button');
    if (!optimizeButton || !submitButton) {
      throw new Error('Missing report buttons');
    }

    optimizeButton.click();
    await flushUi();
    submitButton.click();
    await flushUi();

    expect(apiMocks.optimizeManualReportComments.mock.calls[0][0].transcript_excerpt).toBe(
      'Fetched transcript evidence from captions.',
    );
    expect(apiMocks.sendFeedbackEvent.mock.calls[0][0].manual_report.transcript_excerpt).toBe(
      'Fetched transcript evidence from captions.',
    );
  });

  it('preserves concrete thumbnail text when optimization returns generic wording', async () => {
    const concreteThumbnailObservation =
      'Thumbnail contains an explicit high-severity accusation involving children, and the wording itself is inappropriate and harmful as public thumbnail text. It may also misrepresent the actual content and create a misleading accusation.';
    const thumbnailOnlyDraft = makeSuggestion('report', false);
    thumbnailOnlyDraft.issues = thumbnailOnlyDraft.issues.map((issue) => ({
      ...issue,
      suggested: issue.issue_type === 'thumbnail',
      comment: issue.issue_type === 'thumbnail' ? 'Initial thumbnail concern.' : '',
    }));
    apiMocks.suggestManualReportComments.mockResolvedValueOnce(thumbnailOnlyDraft);
    apiMocks.optimizeManualReportComments.mockResolvedValueOnce({
      issues: [
        {
          issue_type: 'thumbnail',
          comment:
            'Thumbnail image may not accurately represent the scenario or subject suggested by the title, which could mislead users about what the video actually shows.',
        },
      ],
      optimization_model: 'gemini-2.5-flash',
      report_text:
        'Please review this video.\n- Thumbnail: Thumbnail image may not accurately represent the scenario or subject suggested by the title.',
      selected_tags: [],
    });

    useOverlayStore.getState().openManualReport(makeTarget('report'));
    await flushUi();

    const thumbnailCard = getIssueCard('Thumbnail');
    const thumbnailComment = thumbnailCard.querySelector<HTMLTextAreaElement>('textarea');
    if (!thumbnailComment) {
      throw new Error('Missing thumbnail comment textarea');
    }
    const valueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      'value',
    )?.set;
    valueSetter?.call(thumbnailComment, concreteThumbnailObservation);
    thumbnailComment.dispatchEvent(new Event('input', { bubbles: true }));
    await flushUi();

    const optimizeYes = document.querySelectorAll<HTMLInputElement>(
      'input[name="truthlens-optimize-choice"]',
    )[0];
    if (!optimizeYes) {
      throw new Error('Missing optimize choice');
    }
    optimizeYes.click();
    await flushUi();

    const optimizeButton = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.truthlens-secondary-button'),
    ).find((button) => button.textContent?.includes('Optimize comments'));
    if (!optimizeButton) {
      throw new Error('Missing optimize button');
    }

    optimizeButton.click();
    await flushUi();

    expect(apiMocks.optimizeManualReportComments.mock.calls[0][0].issues[0].comment).toBe(
      concreteThumbnailObservation,
    );
    expect(thumbnailComment.value).toBe(concreteThumbnailObservation);
    expect(document.body.textContent).toContain('explicit high-severity accusation involving children');
    expect(document.body.textContent).not.toContain('scenario or subject suggested by the title');
  });

  it('lets verify mode switch positive tags and persists the override in feedback', async () => {
    useOverlayStore.getState().openManualReport(makeTarget('verify-transparent'));
    await flushUi();

    const music = getTagCheckbox('Music');
    const documentary = getTagCheckbox('Documentary');
    expect(music.checked).toBe(true);
    expect(documentary.checked).toBe(false);

    music.click();
    documentary.click();
    await flushUi();

    const submitButton = document.querySelector<HTMLButtonElement>('.truthlens-primary-button');
    if (!submitButton) {
      throw new Error('Missing submit button');
    }

    submitButton.click();
    await flushUi();

    expect(apiMocks.sendFeedbackEvent).toHaveBeenCalledTimes(1);
    expect(apiMocks.sendFeedbackEvent.mock.calls[0][0].manual_report.selected_tags).toEqual([
      'Documentary',
    ]);
    expect(apiMocks.sendFeedbackEvent.mock.calls[0][0].manual_report.suggested_tags[0].tag).toBe(
      'Music',
    );
  });

  it('fills selected verify draft comments when the API returns blank issue text', async () => {
    const blankVerifyDraft = makeSuggestion('verify-transparent', false);
    blankVerifyDraft.issues = blankVerifyDraft.issues.map((issue) =>
      issue.issue_type === 'transcript'
        ? issue
        : {
            ...issue,
            suggested: true,
            comment: issue.issue_type === 'title' ? issue.comment : '',
          },
    );
    apiMocks.suggestManualReportComments.mockResolvedValueOnce(blankVerifyDraft);

    useOverlayStore.getState().openManualReport(makeTarget('verify-transparent'));
    await flushUi();

    const commentBoxes = Array.from(
      document.querySelectorAll<HTMLTextAreaElement>('.truthlens-issue-comment'),
    );
    expect(commentBoxes.length).toBeGreaterThanOrEqual(5);
    expect(commentBoxes.every((box) => box.value.trim().length > 0)).toBe(true);
    expect(commentBoxes.some((box) => box.value.includes('Aurora Records'))).toBe(true);
  });

  it('requires collection confirmation before batch verify and stores collection provenance', async () => {
    useOverlayStore.getState().openManualReport(makeTarget('verify-transparent', true));
    await flushUi();

    const submitButton = document.querySelector<HTMLButtonElement>('.truthlens-primary-button');
    const confirmBox = document.querySelector<HTMLInputElement>('.truthlens-collection-confirm input');
    if (!submitButton || !confirmBox) {
      throw new Error('Missing collection controls');
    }

    expect(submitButton.disabled).toBe(true);
    expect(document.body.textContent).toContain('Collection detected (2 visible items). Confirmation is required before batch submit.');

    confirmBox.click();
    await flushUi();

    expect(submitButton.disabled).toBe(false);
    expect(submitButton.textContent).toContain('Verify 2 items');

    submitButton.click();
    await flushUi();

    expect(apiMocks.sendFeedbackEvent).toHaveBeenCalledTimes(3);
    expect(apiMocks.sendFeedbackEvent.mock.calls[0][0].user_action).toBe(
      'confirm-transparent-collection',
    );
    expect(apiMocks.sendFeedbackEvent.mock.calls[0][0].manual_report.collection_scope.apply_to_all).toBe(
      true,
    );
  });

  it('uses the in-page YouTube report flow when direct YouTube API reporting is unavailable for the account', async () => {
    apiMocks.fetchYouTubeAuthStatus.mockResolvedValue({
      configured: true,
      connected: true,
      auth_url: null,
      channel_name: 'TruthLens Test Channel',
      direct_reporting_supported: false,
      direct_reporting_detail:
        "YouTube did not return a suitable 'Spam or misleading' report category for this account.",
    });

    useOverlayStore.getState().openManualReport(makeTarget('report'));
    await flushUi();

    const submitButton = document.querySelector<HTMLButtonElement>('.truthlens-primary-button');
    if (!submitButton) {
      throw new Error('Missing submit button');
    }

    expect(submitButton.disabled).toBe(false);
    vi.useFakeTimers();
    submitButton.click();
    await Promise.resolve();
    await vi.runAllTimersAsync();
    await Promise.resolve();

    expect(apiMocks.submitYouTubeReport).not.toHaveBeenCalled();
    expect(pageReportingMocks.submitYouTubePageReport).toHaveBeenCalledTimes(1);
    expect(apiMocks.sendFeedbackEvent).toHaveBeenCalledTimes(1);
    expect(document.body.textContent).toContain(
      'Rapporten blev sendt via YouTubes indbyggede report-flow under "Spam or misleading" / "Misleading metadata", og TruthLens-feedback blev registreret i den hostede API.',
    );
    expect(document.body.textContent).toContain(
      'TruthLens feedback was recorded by the hosted API.',
    );
    expect(document.body.textContent).toContain(
      'The in-page YouTube report flow completed on the current page.',
    );
  });
});
