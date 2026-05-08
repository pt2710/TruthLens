import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_FEED_RERANK_ENABLED,
  loadFeedRerankEnabled,
  persistFeedRerankEnabled,
} from './feedRerankSettings';

describe('feedRerankSettings', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('defaults to disabled when the storage key is missing', async () => {
    vi.stubGlobal('chrome', {
      storage: {
        local: {
          get: vi.fn(async (key: string) => {
            void key;
            return {};
          }),
          set: vi.fn(async (payload: Record<string, unknown>) => {
            void payload;
          }),
        },
      },
    });

    await expect(loadFeedRerankEnabled()).resolves.toBe(false);
  });

  it('persists and loads the feed reranking toggle through chrome.storage.local', async () => {
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

    await persistFeedRerankEnabled(false);

    await expect(loadFeedRerankEnabled()).resolves.toBe(false);
  });

  it('falls back to the committed default when chrome storage is unavailable', async () => {
    vi.stubGlobal('chrome', undefined);

    await expect(loadFeedRerankEnabled()).resolves.toBe(
      DEFAULT_FEED_RERANK_ENABLED,
    );
  });
});
