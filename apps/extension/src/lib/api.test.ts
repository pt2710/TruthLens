import { beforeEach, describe, expect, it, vi } from 'vitest';

import { scoreFeedItem } from './api';

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
      },
    });

    expect(result.recommended_action).not.toBe('none');
    expect(result.reasons.length).toBeGreaterThan(0);
  });
});
