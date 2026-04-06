import { afterEach, describe, expect, it, vi } from 'vitest';
import { scoreResultSchema } from '@truthlens/shared-schemas';

import {
  DEFAULT_SESSION_STATS,
  type ExtensionSessionStats,
  loadExtensionSessionStats,
  persistExtensionSessionStats,
} from './sessionStats';

describe('sessionStats', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('persists and loads extension session stats through chrome.storage.local', async () => {
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

    const expected: ExtensionSessionStats = {
      itemCount: 12,
      flaggedCount: 5,
      lastScore: scoreResultSchema.parse({
        risk_score: 0.44,
        confidence: 0.79,
        uncertainty: 0.21,
        content_class: 'news',
        content_class_confidence: 0.8,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: [],
          guardrail_applied: 'factual-context-amplifies-mismatch',
        },
        recommended_action: 'badge',
        reasons: ['Example'],
        explanation_id: 'exp-1',
        explanation_summary: 'Example summary',
        evidence: [],
      }),
      updatedAt: '2026-04-01T09:00:00Z',
    };

    await persistExtensionSessionStats(expected);

    await expect(loadExtensionSessionStats()).resolves.toEqual(expected);
  });

  it('returns defaults when chrome storage is unavailable', async () => {
    vi.stubGlobal('chrome', undefined);

    await expect(loadExtensionSessionStats()).resolves.toEqual(DEFAULT_SESSION_STATS);
  });
});
