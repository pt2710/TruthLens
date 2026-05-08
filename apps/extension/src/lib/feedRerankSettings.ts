const FEED_RERANK_ENABLED_KEY = 'truthlens-feed-rerank-enabled';

// Public beta: local feed reranking is opt-in and must be OFF by default.
export const DEFAULT_FEED_RERANK_ENABLED = false;

export async function loadFeedRerankEnabled(): Promise<boolean> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return DEFAULT_FEED_RERANK_ENABLED;
  }

  const payload = await chrome.storage.local.get(FEED_RERANK_ENABLED_KEY);
  const value = payload?.[FEED_RERANK_ENABLED_KEY];
  return typeof value === 'boolean' ? value : DEFAULT_FEED_RERANK_ENABLED;
}

export async function persistFeedRerankEnabled(enabled: boolean): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return;
  }

  await chrome.storage.local.set({
    [FEED_RERANK_ENABLED_KEY]: enabled,
  });
}

export {
  FEED_RERANK_ENABLED_KEY,
};
