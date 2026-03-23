import {
  feedbackEventSchema,
  scoreItemRequestSchema,
  scoreResultSchema,
  type FeedbackEvent,
  type ScoreItemRequest,
  type ScoreResult,
} from '@truthlens/shared-schemas';

import { createBootstrapScore } from './mockScore';

const API_BASE = 'http://127.0.0.1:8000';
const scoreCache = new Map<string, ScoreResult>();

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
