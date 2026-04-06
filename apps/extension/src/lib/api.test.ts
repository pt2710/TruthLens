import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  batchScoreFeedItems,
  fetchYouTubeAuthStatus,
  fetchFeedbackSummary,
  optimizeManualReportComments,
  scoreFeedItem,
  suggestManualReportComments,
  submitYouTubeReport,
} from './api';

describe('scoreFeedItem', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('falls back to bootstrap scoring when the API is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    const result = await scoreFeedItem({
      item_id: 'card-1',
      title: 'Breaking aliens confirmed',
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
      });

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
      {
        item_id: 'card-1',
        title: 'Breaking aliens confirmed',
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
      },
      {
        item_id: 'card-2',
        title: 'Weekly launch schedule',
        thumbnail_ref: null,
        metadata: {},
        channel: {
          channel_name: 'Context First Media',
          prior_flags: 0,
          channel_history_features: {},
        },
        user_context: {
          strict_mode: false,
          muted_channels: [],
          prior_corrections: 0,
        },
      },
    ]);

    expect(Object.keys(results)).toHaveLength(2);
    expect(results['card-1'].reasons.length).toBeGreaterThan(0);
    expect(results['card-1'].explanation_id).toBeTruthy();
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
    expect(suggestion.suggestion_model).toBe('gemini-2.5-flash');
    expect(suggestion.issues).toHaveLength(6);
    expect(suggestion.issues.find((issue) => issue.issue_type === 'thumbnail')?.suggested).toBe(true);
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
        }),
      }),
    );

    const status = await fetchYouTubeAuthStatus();

    expect(status.connected).toBe(true);
    expect(status.channel_name).toBe('TruthLens Test Channel');
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
