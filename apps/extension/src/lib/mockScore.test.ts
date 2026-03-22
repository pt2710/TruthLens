import { describe, expect, it } from 'vitest';

import { createBootstrapScore } from './mockScore';

describe('createBootstrapScore', () => {
  it('flags sensational titles', () => {
    const result = createBootstrapScore({
      item_id: 'card-1',
      title: 'Breaking secret aliens confirmed',
      thumbnail_ref: null,
      metadata: {},
      channel: {
        channel_name: 'Channel',
        prior_flags: 1,
      },
    });

    expect(result.risk_score).toBeGreaterThan(0.35);
    expect(result.reasons.length).toBeGreaterThan(0);
  });
});
