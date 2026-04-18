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
      { issue_type: 'transcript', suggested: false, comment: '' },
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
    transcriptExcerpt:
      workflowMode === 'verify-transparent'
        ? 'Lyrics and artist credits remain consistent.'
        : 'The transcript does not support the claim.',
    collectionScope,
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
    apiMocks.sendFeedbackEvent.mockResolvedValue(undefined);
    apiMocks.suggestManualReportComments.mockImplementation(
      async (payload: { workflow_mode: 'report' | 'verify-transparent' }) =>
        makeSuggestion(payload.workflow_mode),
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
      'Rapporten blev sendt via YouTubes indbyggede report-flow under "Spam or misleading" / "Misleading metadata", og TruthLens-feedback blev gemt lokalt.',
    );
    expect(document.body.textContent).toContain(
      'The in-page YouTube report flow completed on the current page.',
    );
  });
});
