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
import { buildTruthLensApiUrl } from './runtimeConfig';

const scoreCache = new Map<string, ScoreResult>();
const SCORE_REQUEST_TIMEOUT_MS = 12000;
const STATUS_REQUEST_TIMEOUT_MS = 3500;
const EVENT_POST_TIMEOUT_MS = 5000;
const MANUAL_REPORT_SUGGEST_TIMEOUT_MS = 25000;
const MANUAL_REPORT_OPTIMIZE_TIMEOUT_MS = 25000;
const YOUTUBE_AUTH_STATUS_TIMEOUT_MS = 5000;
const YOUTUBE_REPORT_TIMEOUT_MS = 5000;
const HOMEPAGE_LOG_PREFIX = '[truthlens:homepage]';
const PENDING_FEEDBACK_EVENTS_KEY = 'truthlens-pending-feedback-events';
const MAX_PENDING_FEEDBACK_EVENTS = 100;

let memoryPendingFeedbackEvents: FeedbackEvent[] = [];

type ChromeStorageAreaCompat = {
  get: (
    keys: string,
    callback?: (items: Record<string, unknown>) => void,
  ) => void | Promise<Record<string, unknown>>;
  set: (
    items: Record<string, unknown>,
    callback?: () => void,
  ) => void | Promise<void>;
};

type BackgroundOptimizeResponse =
  | { ok: true; data: ManualReportOptimizationResponse }
  | { ok: false; error?: string };

type BackgroundFeedbackResponse =
  | { ok: true; status: number }
  | { ok: false; error?: string; status?: number };

export type FeedbackDeliveryResult = {
  status: 'remote' | 'queued';
  transport: 'content-fetch' | 'background-fetch' | 'local-queue';
  queued_count: number;
  flushed_count: number;
  error?: string;
};

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
  effective_sample_count?: number;
  channel_risk_mean?: number;
  repeat_template_rate?: number;
  trust_score?: number;
};

export type FeedbackSummary = {
  total_events: number;
  correction_rate: number;
  channel_profiles?: Record<string, FeedbackChannelProfile>;
  top_channels: FeedbackChannelProfile[];
  local_user_feedback?: {
    total_events: number;
    action_counts: Record<string, number>;
  };
  creator_operator_feedback?: {
    total_events: number;
    candidate_events: number;
    action_counts: Record<string, number>;
    operator_ids: string[];
  };
};

export type { YouTubeAuthStatus, YouTubeReportRequest, YouTubeReportResponse };

function describeError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return String(error);
}

function stableObjectString(value: Record<string, number>): string {
  return JSON.stringify(
    Object.keys(value)
      .sort()
      .reduce<Record<string, number>>((accumulator, key) => {
        accumulator[key] = value[key];
        return accumulator;
      }, {}),
  );
}

function hasChromeStorage(): boolean {
  return (
    typeof chrome !== 'undefined' &&
    Boolean(chrome.storage?.local?.get) &&
    Boolean(chrome.storage?.local?.set)
  );
}

async function getChromeStorageValue<T>(key: string): Promise<T | undefined> {
  if (!hasChromeStorage()) {
    return undefined;
  }

  return new Promise((resolve) => {
    let resolved = false;
    const resolveOnce = (value: T | undefined) => {
      if (resolved) {
        return;
      }
      resolved = true;
      resolve(value);
    };
    try {
      const storage = chrome.storage.local as unknown as ChromeStorageAreaCompat;
      const maybePromise = storage.get(key, (items) => {
        if (chrome.runtime?.lastError) {
          resolveOnce(undefined);
          return;
        }
        resolveOnce(items[key] as T | undefined);
      });
      if (maybePromise && typeof maybePromise.then === 'function') {
        maybePromise
          .then((items) => {
            resolveOnce(items[key] as T | undefined);
          })
          .catch(() => {
            resolveOnce(undefined);
          });
      }
    } catch {
      resolveOnce(undefined);
    }
  });
}

async function setChromeStorageValue<T>(key: string, value: T): Promise<void> {
  if (!hasChromeStorage()) {
    memoryPendingFeedbackEvents = Array.isArray(value)
      ? (value as FeedbackEvent[])
      : memoryPendingFeedbackEvents;
    return;
  }

  await new Promise<void>((resolve) => {
    let resolved = false;
    const resolveOnce = () => {
      if (resolved) {
        return;
      }
      resolved = true;
      resolve();
    };
    try {
      const storage = chrome.storage.local as unknown as ChromeStorageAreaCompat;
      const maybePromise = storage.set({ [key]: value }, resolveOnce);
      if (maybePromise && typeof maybePromise.then === 'function') {
        maybePromise.then(resolveOnce).catch(resolveOnce);
      }
    } catch {
      resolveOnce();
    }
  });
}

async function readPendingFeedbackEvents(): Promise<FeedbackEvent[]> {
  const stored = await getChromeStorageValue<unknown>(PENDING_FEEDBACK_EVENTS_KEY);
  if (!Array.isArray(stored)) {
    return [...memoryPendingFeedbackEvents];
  }

  return stored
    .map((event) => feedbackEventSchema.safeParse(event))
    .filter((result): result is { success: true; data: FeedbackEvent } => result.success)
    .map((result) => result.data);
}

async function writePendingFeedbackEvents(events: FeedbackEvent[]): Promise<void> {
  const boundedEvents = events.slice(-MAX_PENDING_FEEDBACK_EVENTS);
  memoryPendingFeedbackEvents = boundedEvents;
  await setChromeStorageValue(PENDING_FEEDBACK_EVENTS_KEY, boundedEvents);
}

function cacheKey(item: ScoreItemRequest): string {
  return [
    item.item_id,
    item.title,
    item.transcript_excerpt ?? '',
    item.channel.channel_name,
    String(item.channel.prior_flags),
    stableObjectString(item.channel.channel_history_features),
    item.user_context.strict_mode ? 'strict' : 'default',
    item.user_context.muted_channels.join('|'),
  ].join(':');
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  timeoutMs: number,
): Promise<Response> {
  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null;
  try {
    return await Promise.race([
      fetch(input, init),
      new Promise<Response>((_, reject) => {
        timeoutId = globalThis.setTimeout(() => {
          reject(new Error(`TruthLens API request timed out after ${timeoutMs}ms.`));
        }, timeoutMs);
      }),
    ]);
  } finally {
    if (timeoutId !== null) {
      globalThis.clearTimeout(timeoutId);
    }
  }
}

async function postFeedbackDirect(parsedEvent: FeedbackEvent): Promise<void> {
  const response = await fetchWithTimeout(
    buildTruthLensApiUrl('/feedback'),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsedEvent),
    },
    EVENT_POST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw new Error(`Feedback request failed: ${response.status}`);
  }
}

async function postFeedbackViaBackground(parsedEvent: FeedbackEvent): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
    throw new Error('Extension background relay is unavailable.');
  }

  const response = (await chrome.runtime.sendMessage({
    type: 'TRUTHLENS_POST_FEEDBACK',
    payload: parsedEvent,
  })) as BackgroundFeedbackResponse | undefined;

  if (!response?.ok) {
    throw new Error(
      response?.error ??
        (response?.status ? `Feedback background request failed: ${response.status}` : 'Feedback background request failed.'),
    );
  }
}

async function postFeedbackToRemote(
  parsedEvent: FeedbackEvent,
): Promise<'content-fetch' | 'background-fetch'> {
  try {
    await postFeedbackDirect(parsedEvent);
    return 'content-fetch';
  } catch (directError) {
    try {
      await postFeedbackViaBackground(parsedEvent);
      return 'background-fetch';
    } catch (backgroundError) {
      throw new Error(
        `Content fetch failed (${describeError(directError)}); background relay failed (${describeError(
          backgroundError,
        )}).`,
      );
    }
  }
}

async function queueFeedbackEvent(
  parsedEvent: FeedbackEvent,
  error: unknown,
): Promise<FeedbackDeliveryResult> {
  const pendingEvents = await readPendingFeedbackEvents();
  pendingEvents.push(parsedEvent);
  await writePendingFeedbackEvents(pendingEvents);

  return {
    status: 'queued',
    transport: 'local-queue',
    queued_count: Math.min(pendingEvents.length, MAX_PENDING_FEEDBACK_EVENTS),
    flushed_count: 0,
    error: describeError(error),
  };
}

export async function flushPendingFeedbackEvents(): Promise<number> {
  const pendingEvents = await readPendingFeedbackEvents();
  if (pendingEvents.length === 0) {
    return 0;
  }

  const remainingEvents: FeedbackEvent[] = [];
  let flushedCount = 0;
  for (const event of pendingEvents) {
    try {
      await postFeedbackToRemote(event);
      flushedCount += 1;
    } catch {
      remainingEvents.push(event);
    }
  }

  if (flushedCount > 0 || remainingEvents.length !== pendingEvents.length) {
    await writePendingFeedbackEvents(remainingEvents);
  }
  return flushedCount;
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
    const response = await fetchWithTimeout(
      buildTruthLensApiUrl('/score-item'),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsedItem),
      },
      SCORE_REQUEST_TIMEOUT_MS,
    );
    if (!response.ok) {
      throw new Error(`Score request failed: ${response.status}`);
    }
    const payload = scoreResultSchema.parse(await response.json());
    scoreCache.set(key, payload);
    return payload;
  } catch (error) {
    console.info(`${HOMEPAGE_LOG_PREFIX} bootstrap fallback used for /score-item`, {
      itemId: parsedItem.item_id,
      reason: describeError(error),
    });
    return createBootstrapScore(parsedItem);
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
    const response = await fetchWithTimeout(
      buildTruthLensApiUrl('/batch-score'),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: uncachedItems }),
      },
      SCORE_REQUEST_TIMEOUT_MS,
    );
    if (!response.ok) {
      throw new Error(`Batch score request failed: ${response.status}`);
    }
    const payload = batchScoreResponseSchema.parse(await response.json());
    for (const item of uncachedItems) {
      const liveScore = payload.results[item.item_id];
      const score = liveScore ?? createBootstrapScore(item);
      if (liveScore) {
        scoreCache.set(cacheKey(item), liveScore);
      }
      results[item.item_id] = score;
    }
    return results;
  } catch (error) {
    console.info(`${HOMEPAGE_LOG_PREFIX} bootstrap fallback used for /batch-score`, {
      itemCount: uncachedItems.length,
      reason: describeError(error),
    });
    for (const item of uncachedItems) {
      results[item.item_id] = createBootstrapScore(item);
    }
    return results;
  }
}

export async function sendFeedbackEvent(payload: FeedbackEvent): Promise<FeedbackDeliveryResult> {
  const parsedEvent = feedbackEventSchema.parse(payload);
  try {
    const transport = await postFeedbackToRemote(parsedEvent);
    const flushedCount = await flushPendingFeedbackEvents();
    const queuedCount = (await readPendingFeedbackEvents()).length;
    return {
      status: 'remote',
      transport,
      queued_count: queuedCount,
      flushed_count: flushedCount,
    };
  } catch (error) {
    return queueFeedbackEvent(parsedEvent, error);
  }
}

export async function sendBrowserObservation(
  payload: BrowserObservationRecord,
): Promise<void> {
  const parsedObservation = browserObservationRecordSchema.parse(payload);
  try {
    await fetchWithTimeout(
      buildTruthLensApiUrl('/browser-observation'),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsedObservation),
      },
      EVENT_POST_TIMEOUT_MS,
    );
  } catch {
    // Fail soft in the browser; observation intake should never block UI rendering.
  }
}

export async function optimizeManualReportComments(
  payload: ManualReportOptimizationRequest,
): Promise<ManualReportOptimizationResponse> {
  const parsedRequest = manualReportOptimizationRequestSchema.parse(payload);
  try {
    const response = await fetchWithTimeout(
      buildTruthLensApiUrl('/manual-report/optimize'),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsedRequest),
      },
      MANUAL_REPORT_OPTIMIZE_TIMEOUT_MS,
    );
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
  const response = await fetchWithTimeout(
    buildTruthLensApiUrl('/manual-report/suggest'),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsedRequest),
    },
    MANUAL_REPORT_SUGGEST_TIMEOUT_MS,
  );
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
    const response = await fetchWithTimeout(
      buildTruthLensApiUrl('/model-info'),
      undefined,
      STATUS_REQUEST_TIMEOUT_MS,
    );
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
    const response = await fetchWithTimeout(
      buildTruthLensApiUrl('/policy-info'),
      undefined,
      STATUS_REQUEST_TIMEOUT_MS,
    );
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
    const response = await fetchWithTimeout(
      buildTruthLensApiUrl('/feedback-summary'),
      undefined,
      STATUS_REQUEST_TIMEOUT_MS,
    );
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
  const response = await fetchWithTimeout(
    buildTruthLensApiUrl('/youtube/auth/status'),
    undefined,
    YOUTUBE_AUTH_STATUS_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw new Error(`YouTube auth status request failed: ${response.status}`);
  }
  return youtubeAuthStatusSchema.parse(await response.json());
}

export async function submitYouTubeReport(
  payload: YouTubeReportRequest,
): Promise<YouTubeReportResponse> {
  const parsedRequest = youtubeReportRequestSchema.parse(payload);
  const response = await fetchWithTimeout(
    buildTruthLensApiUrl('/youtube/report'),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsedRequest),
    },
    YOUTUBE_REPORT_TIMEOUT_MS,
  );
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

export function __resetExtensionApiStateForTests(): void {
  scoreCache.clear();
  memoryPendingFeedbackEvents = [];
}
