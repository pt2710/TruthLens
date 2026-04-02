import type { ScoreResult } from '@truthlens/shared-schemas';

const SESSION_STATS_KEY = 'truthlens-session-stats';

export type ExtensionSessionStats = {
  itemCount: number;
  flaggedCount: number;
  lastScore: ScoreResult | null;
  updatedAt: string | null;
};

export const DEFAULT_SESSION_STATS: ExtensionSessionStats = {
  itemCount: 0,
  flaggedCount: 0,
  lastScore: null,
  updatedAt: null,
};

export async function loadExtensionSessionStats(): Promise<ExtensionSessionStats> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return DEFAULT_SESSION_STATS;
  }

  const payload = await chrome.storage.local.get(SESSION_STATS_KEY);
  const stats = payload?.[SESSION_STATS_KEY] as ExtensionSessionStats | undefined;
  return stats ?? DEFAULT_SESSION_STATS;
}

export async function persistExtensionSessionStats(
  stats: ExtensionSessionStats,
): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return;
  }

  await chrome.storage.local.set({
    [SESSION_STATS_KEY]: stats,
  });
}
