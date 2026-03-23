import {
  batchScoreRequestSchema,
  batchScoreResponseSchema,
  feedbackEventSchema,
  scoreItemRequestSchema,
  scoreResultSchema,
  type BatchScoreRequest,
  type FeedbackEvent,
  type ScoreItemRequest,
  type ScoreResult,
} from '@truthlens/shared-schemas';

import { createBootstrapScore } from './mockScore';

const API_BASE = 'http://127.0.0.1:8000';
const scoreCache = new Map<string, ScoreResult>();

export type ModelInfo = {
  mode: string;
  model_version?: string;
  available_heads?: string[];
};

export type PolicyInfo = {
  policy_version: string;
  effective_thresholds: Record<string, number>;
  feedback_summary?: {
    total_events: number;
    correction_rate: number;
    top_channels: Array<{
      channel_name: string;
      event_count: number;
      bias: number;
      report_count: number;
      dismiss_count: number;
      mute_count: number;
    }>;
  };
};

export type FeedbackSummary = {
  total_events: number;
  correction_rate: number;
  top_channels: Array<{
    channel_name: string;
    event_count: number;
    bias: number;
    report_count: number;
    dismiss_count: number;
    mute_count: number;
  }>;
};

function cacheKey(item: ScoreItemRequest): string {
  return [
    item.item_id,
    item.title,
    item.transcript_excerpt ?? '',
    item.channel.channel_name,
    String(item.channel.prior_flags),
    item.user_context.strict_mode ? 'strict' : 'default',
    item.user_context.muted_channels.join('|'),
  ].join(':');
}

export async function scoreFeedItem(item: ScoreItemRequest): Promise<ScoreResult> {
  const parsedItem = scoreItemRequestSchema.parse(item);
  const key = cacheKey(parsedItem);
  const cached = scoreCache.get(key);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(`${API_BASE}/score-item`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsedItem),
    });
    if (!response.ok) {
      throw new Error(`Score request failed: ${response.status}`);
    }
    const payload = scoreResultSchema.parse(await response.json());
    scoreCache.set(key, payload);
    return payload;
  } catch {
    const fallback = createBootstrapScore(parsedItem);
    scoreCache.set(key, fallback);
    return fallback;
  }
}

export async function batchScoreFeedItems(items: ScoreItemRequest[]): Promise<Record<string, ScoreResult>> {
  const parsedRequest = batchScoreRequestSchema.parse({ items }) as BatchScoreRequest;
  const results: Record<string, ScoreResult> = {};
  const uncachedItems: ScoreItemRequest[] = [];

  for (const item of parsedRequest.items) {
    const key = cacheKey(item);
    const cached = scoreCache.get(key);
    if (cached) {
      results[item.item_id] = cached;
      continue;
    }
    uncachedItems.push(item);
  }

  if (uncachedItems.length === 0) {
    return results;
  }

  try {
    const response = await fetch(`${API_BASE}/batch-score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: uncachedItems }),
    });
    if (!response.ok) {
      throw new Error(`Batch score request failed: ${response.status}`);
    }
    const payload = batchScoreResponseSchema.parse(await response.json());
    for (const item of uncachedItems) {
      const score = payload.results[item.item_id] ?? createBootstrapScore(item);
      scoreCache.set(cacheKey(item), score);
      results[item.item_id] = score;
    }
    return results;
  } catch {
    for (const item of uncachedItems) {
      const fallback = createBootstrapScore(item);
      scoreCache.set(cacheKey(item), fallback);
      results[item.item_id] = fallback;
    }
    return results;
  }
}

export async function sendFeedbackEvent(payload: FeedbackEvent): Promise<void> {
  const parsedEvent = feedbackEventSchema.parse(payload);
  try {
    await fetch(`${API_BASE}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsedEvent),
    });
  } catch {
    // Fail soft in the browser; feedback is advisory and should not block UI interaction.
  }
}

export async function fetchModelInfo(): Promise<ModelInfo> {
  try {
    const response = await fetch(`${API_BASE}/model-info`);
    if (!response.ok) {
      throw new Error(`Model info request failed: ${response.status}`);
    }
    return (await response.json()) as ModelInfo;
  } catch {
    return { mode: 'bootstrap', model_version: 'extension-fallback' };
  }
}

export async function fetchPolicyInfo(): Promise<PolicyInfo> {
  try {
    const response = await fetch(`${API_BASE}/policy-info`);
    if (!response.ok) {
      throw new Error(`Policy info request failed: ${response.status}`);
    }
    return (await response.json()) as PolicyInfo;
  } catch {
    return {
      policy_version: 'extension-fallback',
      effective_thresholds: {
        badge_threshold: 0.35,
        blur_threshold: 0.6,
        report_prompt_threshold: 0.8,
        hide_threshold: 0.93,
      },
      feedback_summary: {
        total_events: 0,
        correction_rate: 0,
        top_channels: [],
      },
    };
  }
}

export async function fetchFeedbackSummary(): Promise<FeedbackSummary> {
  try {
    const response = await fetch(`${API_BASE}/feedback-summary`);
    if (!response.ok) {
      throw new Error(`Feedback summary request failed: ${response.status}`);
    }
    return (await response.json()) as FeedbackSummary;
  } catch {
    return {
      total_events: 0,
      correction_rate: 0,
      top_channels: [],
    };
  }
}
