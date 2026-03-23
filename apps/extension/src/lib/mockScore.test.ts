import { describe, expect, it } from 'vitest';

import { createBootstrapScore } from './mockScore';

describe('createBootstrapScore', () => {
  it('flags sensational titles', () => {
    const result = createBootstrapScore({
      item_id: 'card-1',
      title: 'Breaking secret aliens confirmed',
      thumbnail_ref: null,
      transcript_excerpt: null,
      metadata: {},
      channel: {
        channel_name: 'Channel',
        prior_flags: 1,
        channel_history_features: {},
      },
      user_context: {
        strict_mode: false,
        muted_channels: [],
        prior_corrections: 0,
      },
    });

    expect(result.risk_score).toBeGreaterThan(0.35);
    expect(result.reasons.length).toBeGreaterThan(0);
    expect(result.explanation_id).toBeTruthy();
    expect(result.evidence.length).toBeGreaterThan(0);
  });

  it('hides muted channels immediately', () => {
    const result = createBootstrapScore({
      item_id: 'card-2',
      title: 'Weekly launch schedule',
      thumbnail_ref: null,
      transcript_excerpt: null,
      metadata: {},
      channel: {
        channel_name: 'Muted Channel',
        prior_flags: 0,
        channel_history_features: {},
      },
      user_context: {
        strict_mode: false,
        muted_channels: ['Muted Channel'],
        prior_corrections: 0,
      },
    });

    expect(result.recommended_action).toBe('hide');
    expect(result.reasons[0]).toContain('muted');
    expect(result.explanation_summary).toContain('muted');
  });
});
