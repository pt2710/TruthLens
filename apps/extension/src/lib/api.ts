import {
  batchScoreRequestSchema,
  batchScoreResponseSchema,
  browserObservationRecordSchema,
  feedbackEventSchema,
  manualReportOptimizationRequestSchema,
  manualReportOptimizationResponseSchema,
  manualReportSuggestionRequestSchema,
  manualReportSuggestionResponseSchema,
  scoreItemRequestSchema,
  scoreResultSchema,
  youtubeAuthStatusSchema,
  youtubeReportRequestSchema,
  youtubeReportResponseSchema,
  type BatchScoreRequest,
  type BrowserObservationRecord,
  type FeedbackEvent,
  type ManualReportOptimizationRequest,
  type ManualReportOptimizationResponse,
  type ManualReportSuggestionRequest,
  type ManualReportSuggestionResponse,
  type ScoreItemRequest,
  type ScoreResult,
  type YouTubeAuthStatus,
  type YouTubeReportRequest,
  type YouTubeReportResponse,
} from '@truthlens/shared-schemas';

import { createBootstrapScore } from './mockScore';

const API_BASE = 'http://127.0.0.1:8000';
const scoreCache = new Map<string, ScoreResult>();

type BackgroundOptimizeResponse =
  | { ok: true; data: ManualReportOptimizationResponse }
  | { ok: false; error?: string };

export type ModelInfo = {
  mode: string;
  model_version?: string;
  artifact_status?: string;
  architecture_plan_version?: string;
  available_heads?: string[];
  head_specs?: Array<{
    name: string;
    family: string;
    backend: string;
  }>;
  architecture_layers?: Array<{
    component_id: string;
    label: string;
    phase: string;
    status: string;
    layer_type: string;
    family: string;
    encoder: string;
    backend: string;
    runtime_path: string;
  }>;
  text_encoder_resolution?: {
    requested_encoder: string;
    actual_encoder: string;
    fallback_used: boolean;
    sentence_transformer_model?: string | null;
    fallback_reason?: string | null;
  };
  vision_encoder_resolution?: {
    requested_encoder: string;
    actual_encoder: string;
    fallback_used: boolean;
    image_size: number;
    conv_channels: number[];
    hidden_dim: number;
    fallback_reason?: string | null;
  };
  history_encoder_resolution?: {
    requested_encoder: string;
    actual_encoder: string;
    fallback_used: boolean;
    sequence_length: number;
    hidden_dim: number;
    num_layers: number;
    fallback_reason?: string | null;
  };
};

export type PolicyInfo = {
  policy_version: string;
  policy_mode?: string;
  resolved_policy_mode?: string;
  effective_thresholds: Record<string, number>;
  bseo_artifact?: {
    available: boolean;
    compatible: boolean;
    stale?: boolean;
    policy_version?: string;
  };
  feedback_summary?: {
    total_events: number;
    correction_rate: number;
    top_channels: FeedbackChannelProfile[];
  };
};

export type FeedbackChannelProfile = {
  channel_name: string;
  event_count: number;
  bias: number;
  report_count: number;
  dismiss_count: number;
  mute_count: number;
  transparent_count?: number;
  moderate_request_count?: number;
  remove_request_count?: number;
  scored_item_count?: number;
  reported_item_count?: number;
  trust_score?: number;
};

export type FeedbackSummary = {
  total_events: number;
  correction_rate: number;
  channel_profiles?: Record<string, FeedbackChannelProfile>;
  top_channels: FeedbackChannelProfile[];
};

export type { YouTubeAuthStatus, YouTubeReportRequest, YouTubeReportResponse };

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

export async function scoreFeedItem(
  item: ScoreItemRequest,
): Promise<ScoreResult> {
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

export async function batchScoreFeedItems(
  items: ScoreItemRequest[],
): Promise<Record<string, ScoreResult>> {
  const parsedRequest = batchScoreRequestSchema.parse({
    items,
  }) as BatchScoreRequest;
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

export async function sendBrowserObservation(
  payload: BrowserObservationRecord,
): Promise<void> {
  const parsedObservation = browserObservationRecordSchema.parse(payload);
  try {
    await fetch(`${API_BASE}/browser-observation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsedObservation),
    });
  } catch {
    // Fail soft in the browser; observation intake should never block UI rendering.
  }
}

export async function optimizeManualReportComments(
  payload: ManualReportOptimizationRequest,
): Promise<ManualReportOptimizationResponse> {
  const parsedRequest = manualReportOptimizationRequestSchema.parse(payload);
  try {
    const response = await fetch(`${API_BASE}/manual-report/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsedRequest),
    });
    if (!response.ok) {
      let detail = `Manual report optimization failed: ${response.status}`;
      try {
        const payload = (await response.json()) as { detail?: string };
        if (payload.detail) {
          detail = payload.detail;
        }
      } catch {
        // Fall back to status text only.
      }
      throw new Error(detail);
    }
    return manualReportOptimizationResponseSchema.parse(await response.json());
  } catch (error) {
    if (typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
      throw error;
    }

    const response = (await chrome.runtime.sendMessage({
      type: 'TRUTHLENS_OPTIMIZE_MANUAL_REPORT',
      payload: parsedRequest,
    })) as BackgroundOptimizeResponse | undefined;

    if (!response?.ok) {
      throw new Error(response?.error ?? 'Manual report optimization failed.');
    }

    return manualReportOptimizationResponseSchema.parse(response.data);
  }
}

export async function suggestManualReportComments(
  payload: ManualReportSuggestionRequest,
): Promise<ManualReportSuggestionResponse> {
  const parsedRequest = manualReportSuggestionRequestSchema.parse(payload);
  const response = await fetch(`${API_BASE}/manual-report/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(parsedRequest),
  });
  if (!response.ok) {
    let detail = `Manual report suggestions failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep the default message when the backend body cannot be parsed.
    }
    throw new Error(detail);
  }
  return manualReportSuggestionResponseSchema.parse(await response.json());
}

export async function fetchModelInfo(): Promise<ModelInfo> {
  try {
    const response = await fetch(`${API_BASE}/model-info`);
    if (!response.ok) {
      throw new Error(`Model info request failed: ${response.status}`);
    }
    return (await response.json()) as ModelInfo;
  } catch {
    return {
      mode: 'bootstrap',
      model_version: 'extension-fallback',
      artifact_status: 'missing',
    };
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

export async function fetchYouTubeAuthStatus(): Promise<YouTubeAuthStatus> {
  const response = await fetch(`${API_BASE}/youtube/auth/status`);
  if (!response.ok) {
    throw new Error(`YouTube auth status request failed: ${response.status}`);
  }
  return youtubeAuthStatusSchema.parse(await response.json());
}

export async function submitYouTubeReport(
  payload: YouTubeReportRequest,
): Promise<YouTubeReportResponse> {
  const parsedRequest = youtubeReportRequestSchema.parse(payload);
  const response = await fetch(`${API_BASE}/youtube/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(parsedRequest),
  });
  if (!response.ok) {
    let detail = `YouTube report submission failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep the default message when the backend body cannot be parsed.
    }
    throw new Error(detail);
  }
  return youtubeReportResponseSchema.parse(await response.json());
}
