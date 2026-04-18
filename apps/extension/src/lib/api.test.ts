import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ScoreItemRequest } from '@truthlens/shared-schemas';

import {
  __resetExtensionApiStateForTests,
  batchScoreFeedItems,
  fetchYouTubeAuthStatus,
  fetchFeedbackSummary,
  optimizeManualReportComments,
  scoreFeedItem,
  suggestManualReportComments,
  submitYouTubeReport,
} from './api';

function makeScoreItem(itemId: string, title: string): ScoreItemRequest {
  return {
    item_id: itemId,
    title,
    thumbnail_ref: null,
    metadata: {},
    channel: {
      channel_name: 'Test channel',
      prior_flags: 1,
      channel_history_features: {},
    },
    user_context: {
      strict_mode: false,
      muted_channels: [],
      prior_corrections: 0,
    },
    runtime_context: {
      surface: 'unknown',
      review_requested: false,
      source_provenance: null,
    },
  };
}

describe('scoreFeedItem', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    __resetExtensionApiStateForTests();
  });

  it('falls back to bootstrap batch scoring when the API hangs', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => {})));

    const promise = batchScoreFeedItems([
      makeScoreItem('card-1', 'Breaking aliens confirmed'),
    ]);

    await vi.advanceTimersByTimeAsync(13000);
    const results = await promise;

    expect(Object.keys(results)).toHaveLength(1);
    expect(results['card-1'].reasons.length).toBeGreaterThan(0);
  });

  it('falls back to bootstrap scoring when the API is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    const result = await scoreFeedItem(makeScoreItem('card-2', 'Breaking aliens confirmed'));

    expect(result.recommended_action).not.toBe('none');
    expect(result.reasons.length).toBeGreaterThan(0);
    expect(result.explanation_id).toBeTruthy();
    expect(result.explanation_summary).toBeTruthy();
  });

  it('returns an empty feedback summary when the API is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    const summary = await fetchFeedbackSummary();

    expect(summary.total_events).toBe(0);
    expect(summary.top_channels).toEqual([]);
  });

  it('falls back to bootstrap batch scoring when the API is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    const results = await batchScoreFeedItems([
      makeScoreItem('card-3', 'Breaking aliens confirmed'),
      {
        ...makeScoreItem('card-4', 'Weekly launch schedule'),
        channel: {
          channel_name: 'Context First Media',
          prior_flags: 0,
          channel_history_features: {},
        },
      },
    ]);

    expect(Object.keys(results)).toHaveLength(2);
    expect(results['card-3'].reasons.length).toBeGreaterThan(0);
    expect(results['card-3'].explanation_id).toBeTruthy();
  });

  it('does not cache bootstrap fallback after a batch timeout', async () => {
    vi.useFakeTimers();
    const item = makeScoreItem('card-timeout', 'Breaking aliens confirmed');
    const hangingFetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    vi.stubGlobal('fetch', hangingFetch);

    const timedOutPromise = batchScoreFeedItems([item]);
    await vi.advanceTimersByTimeAsync(13000);
    const timedOutResults = await timedOutPromise;

    expect(timedOutResults['card-timeout'].reasons.length).toBeGreaterThan(0);
    expect(hangingFetch).toHaveBeenCalledTimes(1);

    const liveFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: {
          'card-timeout': {
            risk_score: 0.74,
            confidence: 0.88,
            uncertainty: 0.12,
            recommended_action: 'blur',
            reasons: ['Live API scoring recovered after the timeout.'],
            explanation_id: 'exp-live',
            explanation_summary: 'Live API scoring recovered after the timeout.',
            evidence: [],
          },
        },
      }),
    });
    vi.stubGlobal('fetch', liveFetch);

    const liveResults = await batchScoreFeedItems([item]);

    expect(liveFetch).toHaveBeenCalledTimes(1);
    expect(liveResults['card-timeout'].risk_score).toBe(0.74);
    expect(liveResults['card-timeout'].recommended_action).toBe('blur');
  });

  it('surfaces manual report optimization failures with the API detail message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Gemini optimization is not configured for this API.' }),
      }),
    );

    await expect(
      optimizeManualReportComments({
        workflow_mode: 'report',
        target_url: 'https://www.youtube.com/watch?v=card-1',
        title_snapshot: 'Breaking aliens confirmed',
        channel_name: 'Test channel',
        transcript_excerpt: 'A transcript excerpt.',
        requested_outcome: 'moderate',
        selected_tags: [],
        issues: [{ issue_type: 'title', comment: 'The title makes a misleading certainty claim.' }],
      }),
    ).rejects.toThrow('Gemini optimization is not configured for this API.');
  });

  it('falls back to the background worker when direct optimization fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    vi.stubGlobal('chrome', {
      runtime: {
        sendMessage: vi.fn().mockResolvedValue({
          ok: true,
          data: {
            issues: [
              {
                issue_type: 'title',
                comment: 'The title frames an unverified allegation as established fact.',
              },
            ],
            optimization_model: 'gemini-2.5-flash',
            report_text:
              'Please review this video for misleading framing.\n- Title: The title frames an unverified allegation as established fact.',
          },
        }),
      },
    });

    const optimized = await optimizeManualReportComments({
      workflow_mode: 'report',
      target_url: 'https://www.youtube.com/watch?v=card-1',
      title_snapshot: 'Breaking aliens confirmed',
      channel_name: 'Test channel',
      transcript_excerpt: 'A transcript excerpt.',
      requested_outcome: 'moderate',
      selected_tags: [],
      issues: [{ issue_type: 'title', comment: 'The title makes a misleading certainty claim.' }],
    });

    expect(optimized.optimization_model).toBe('gemini-2.5-flash');
    expect(optimized.issues[0].comment).toContain('unverified allegation');
  });

  it('fetches structured manual report draft suggestions from the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          issues: [
            {
              issue_type: 'thumbnail',
              suggested: true,
              comment: 'The thumbnail framing appears disconnected from the stated topic.',
            },
            {
              issue_type: 'title',
              suggested: true,
              comment: 'The title overstates certainty relative to the available context.',
            },
            { issue_type: 'description', suggested: false, comment: '' },
            { issue_type: 'transcript', suggested: false, comment: '' },
            { issue_type: 'channel', suggested: false, comment: '' },
            { issue_type: 'other', suggested: true, comment: 'The packaging resembles clickbait.' },
          ],
          suggested_outcome: 'moderate',
          suggested_outcome_reason:
            'TruthLens recommends Moderate because the packaging overpromises relative to the visible context.',
          suggested_tags: [
            {
              tag: 'Clickbait',
              selected: true,
              confidence: 0.88,
              rationale: 'Report mode defaults to Clickbait.',
            },
          ],
          suggestion_model: 'gemini-2.5-flash',
        }),
      }),
    );

    const suggestion = await suggestManualReportComments({
      workflow_mode: 'report',
      target_url: 'https://www.youtube.com/watch?v=card-1',
      title_snapshot: 'Breaking aliens confirmed',
      channel_name: 'Test channel',
      transcript_excerpt: 'A transcript excerpt.',
      explanation_summary: 'The title and thumbnail appear weakly aligned.',
      reasons: ['Title contains sensational framing patterns.'],
      content_class: 'news',
      content_class_confidence: 0.84,
      bias_profile: {
        metrics: { sensational_weight: 0.72 },
        positive_biases: ['factual-scrutiny'],
        negative_biases: ['sensational-overweighting'],
        guardrail_applied: 'factual-context-amplifies-mismatch',
      },
    });

    expect(suggestion.suggested_outcome).toBe('moderate');
    expect(suggestion.suggested_outcome_reason).toContain('packaging');
    expect(suggestion.suggestion_model).toBe('gemini-2.5-flash');
    expect(suggestion.issues).toHaveLength(6);
    expect(suggestion.suggested_tags[0]?.tag).toBe('Clickbait');
    expect(suggestion.issues.find((issue) => issue.issue_type === 'thumbnail')?.suggested).toBe(true);
  });

  it('allows manual report suggestion requests to complete after 6 seconds', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => ({
                  issues: [
                    { issue_type: 'thumbnail', suggested: true, comment: 'Thumb mismatch.' },
                    { issue_type: 'title', suggested: true, comment: 'Title mismatch.' },
                    { issue_type: 'description', suggested: false, comment: '' },
                    { issue_type: 'transcript', suggested: false, comment: '' },
                    { issue_type: 'channel', suggested: false, comment: '' },
                    { issue_type: 'other', suggested: true, comment: 'Packaging mismatch.' },
                  ],
                  suggested_outcome: 'moderate',
                  suggested_outcome_reason: 'Delayed but valid suggestion payload.',
                  suggested_tags: [
                    {
                      tag: 'Clickbait',
                      selected: true,
                      confidence: 0.91,
                      rationale: 'Report mode defaults to Clickbait.',
                    },
                  ],
                  suggestion_model: 'gemini-2.5-flash',
                }),
              });
            }, 6000);
          }),
      ),
    );

    const suggestionPromise = suggestManualReportComments({
      workflow_mode: 'report',
      target_url: 'https://www.youtube.com/watch?v=card-delayed',
      title_snapshot: 'Delayed report draft',
      channel_name: 'Test channel',
      transcript_excerpt: 'A transcript excerpt.',
      explanation_summary: 'The title and thumbnail appear weakly aligned.',
      reasons: ['Title contains sensational framing patterns.'],
      content_class: 'news',
      content_class_confidence: 0.84,
      bias_profile: {
        metrics: { sensational_weight: 0.72 },
        positive_biases: ['factual-scrutiny'],
        negative_biases: ['sensational-overweighting'],
        guardrail_applied: 'factual-context-amplifies-mismatch',
      },
    });

    await vi.advanceTimersByTimeAsync(7000);
    const suggestion = await suggestionPromise;

    expect(suggestion.suggestion_model).toBe('gemini-2.5-flash');
    expect(suggestion.suggested_outcome_reason).toContain('Delayed');
  });

  it('allows manual report optimization requests to complete after 7 seconds', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => ({
                  issues: [
                    {
                      issue_type: 'title',
                      comment: 'The title frames an unverified allegation as established fact.',
                    },
                  ],
                  optimization_model: 'gemini-2.5-flash',
                  report_text: 'Delayed optimization result.',
                }),
              });
            }, 7000);
          }),
      ),
    );

    const optimizePromise = optimizeManualReportComments({
      workflow_mode: 'report',
      target_url: 'https://www.youtube.com/watch?v=card-1',
      title_snapshot: 'Breaking aliens confirmed',
      channel_name: 'Test channel',
      transcript_excerpt: 'A transcript excerpt.',
      requested_outcome: 'moderate',
      selected_tags: [],
      issues: [{ issue_type: 'title', comment: 'The title makes a misleading certainty claim.' }],
    });

    await vi.advanceTimersByTimeAsync(8000);
    const optimized = await optimizePromise;

    expect(optimized.optimization_model).toBe('gemini-2.5-flash');
    expect(optimized.report_text).toBe('Delayed optimization result.');
  });

  it('fetches YouTube auth status from the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          configured: true,
          connected: true,
          auth_url: null,
          channel_name: 'TruthLens Test Channel',
          direct_reporting_supported: true,
          direct_reporting_detail: 'Direct YouTube API reporting is available for this account.',
        }),
      }),
    );

    const status = await fetchYouTubeAuthStatus();

    expect(status.connected).toBe(true);
    expect(status.channel_name).toBe('TruthLens Test Channel');
    expect(status.direct_reporting_supported).toBe(true);
  });

  it('submits a direct YouTube report through the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: 'reported',
          reason_id: 'MISLEADING',
          reason_label: 'Spam or misleading',
          secondary_reason_id: 'CLICKBAIT',
          secondary_reason_label: 'Misleading metadata',
        }),
      }),
    );

    const result = await submitYouTubeReport({
      target_url: 'https://www.youtube.com/watch?v=card-1',
      report_text: 'Please review this video for misleading framing.',
      issue_types: ['title', 'thumbnail'],
    });

    expect(result.status).toBe('reported');
    expect(result.reason_label).toBe('Spam or misleading');
  });
});
