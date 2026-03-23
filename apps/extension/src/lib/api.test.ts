import { beforeEach, describe, expect, it, vi } from 'vitest';

import { batchScoreFeedItems, fetchFeedbackSummary, scoreFeedItem } from './api';

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
});
