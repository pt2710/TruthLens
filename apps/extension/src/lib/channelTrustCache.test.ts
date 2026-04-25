import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  loadCachedChannelTrustProfiles,
  persistCachedChannelTrustProfiles,
} from './channelTrustCache';

describe('channelTrustCache', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('persists and reloads cached channel trust profiles via chrome.storage.local', async () => {
    const storage = new Map<string, unknown>();
    vi.stubGlobal('chrome', {
      storage: {
        local: {
          get: vi.fn(async (key: string) => ({
            [key]: storage.get(key),
          })),
          set: vi.fn(async (payload: Record<string, unknown>) => {
            Object.entries(payload).forEach(([key, value]) => storage.set(key, value));
          }),
        },
      },
    });

    await persistCachedChannelTrustProfiles({
      'ai revolution': {
        channel_name: 'AI Revolution',
        event_count: 3,
        bias: -0.1,
        report_count: 3,
        dismiss_count: 0,
        mute_count: 0,
        scored_item_count: 6,
        reported_item_count: 3,
        trust_score: 2.9,
      },
    });

    await expect(loadCachedChannelTrustProfiles()).resolves.toEqual({
      'ai revolution': {
        channel_name: 'AI Revolution',
        event_count: 3,
        bias: -0.1,
        report_count: 3,
        dismiss_count: 0,
        mute_count: 0,
        scored_item_count: 6,
        reported_item_count: 3,
        trust_score: 2.9,
      },
    });
  });

  it('returns an empty cache when chrome storage is unavailable', async () => {
    vi.stubGlobal('chrome', undefined);

    await expect(loadCachedChannelTrustProfiles()).resolves.toEqual({});
  });
});
