import React from 'react';
import { createRoot } from 'react-dom/client';
import type {
  BrowserObservationRecord,
  ManualReportIssueType,
  ManualReportWorkflowMode,
  ManualReviewCollectionMember,
  ManualReviewCollectionScope,
  ScoreItemRequest,
  ScoreResult,
} from '@truthlens/shared-schemas';

import {
  batchScoreFeedItems,
  fetchFeedbackSummary,
  sendBrowserObservation,
  sendFeedbackEvent,
  type FeedbackChannelProfile,
} from './lib/api';
import {
  buildChannelHistoryFeatures,
  priorFlagsFromProfile,
} from './lib/feedScoreTruth';
import type { TruthBand } from './lib/feedScoreTruth';
import {
  buildFeedPresentationSnapshot,
  planStableRerankOrder,
  type FeedPresentationSnapshot,
} from './lib/feedReranking';
import {
  DEFAULT_FEED_RERANK_ENABLED,
  FEED_RERANK_ENABLED_KEY,
  loadFeedRerankEnabled,
} from './lib/feedRerankSettings';
import {
  loadCachedChannelTrustProfiles,
  persistCachedChannelTrustProfiles,
} from './lib/channelTrustCache';
import {
  buildStableFeedCardSignature,
  isReadyForStableFeedScoring,
} from './lib/feedCardStability';
import {
  buildPersonalizationSnapshot,
  shouldShowPersonalizationBadge,
  type PersonalizationSnapshot,
} from './lib/personalization';
import {
  collectSafePendingEntries,
  HOMEPAGE_STARTUP_RETRY_DELAY_MS,
  shouldScheduleHomepageStartupRetry,
  type HomepageScoreTrigger,
} from './lib/homepageScoring';
import { createHomepageScoreScheduler } from './lib/homepageScheduler';
import { inferReviewPromptDecision } from './lib/reviewPrompts';
import {
  MANUAL_REVIEW_SUBMITTED_EVENT,
  registerManualReviewSubmittedHandler,
  type ManualReviewSubmittedDetail,
  type ManualReviewSubmittedTarget,
} from './lib/manualReviewEvents';
import { adjustScoreForReportedContent } from './lib/reportFeedbackScoring';
import { shouldRescoreFromMutations } from './lib/domMutationFilter';
import { buildUserContext, isChannelMuted, muteChannel } from './lib/userPreferences';
import { App } from './overlay/App';
import { type ManualReportTarget, useOverlayStore } from './overlay/store';
import {
  submitYouTubePageReportInDocument,
  type YouTubePageReportResult,
} from './lib/youtubePageReporting';
import './styles.css';

const OVERLAY_ID = 'truthlens-overlay-root';
const PROCESSED = 'data-truthlens-processed';
const PROCESSING = 'data-truthlens-processing';
const ITEM_ID = 'data-truthlens-item-id';
const SIGNATURE = 'data-truthlens-signature';
const PERSONALIZATION = 'data-truthlens-personalization';
const PERSONALIZATION_SCORE = 'data-truthlens-personalization-score';
const TRUTH_SCORE = 'data-truthlens-truth-score';
const FEED_RISK_SCORE = 'data-truthlens-feed-risk-score';
const RUNTIME_SCORE = 'data-truthlens-runtime-score';
const TRUTH_BAND = 'data-truthlens-truth-band';
const RERANK_PRIORITY = 'data-truthlens-rerank-priority';
const RERANK_LOCKED = 'data-truthlens-rerank-locked';
const RERANK_CHUNK_ID = 'data-truthlens-rerank-chunk-id';
const RERANK_CHUNK_SEALED = 'data-truthlens-rerank-sealed';
const ORIGINAL_INDEX = 'data-truthlens-original-index';
const OBSERVATION_ID = 'data-truthlens-observation-id';
const SUPPRESSED = 'data-truthlens-suppressed';
const UNKNOWN_CHANNEL_NAME = 'Unknown channel';
const CARD_SELECTOR = 'ytd-rich-item-renderer, ytd-video-renderer, [data-truthlens-card]';
const MUSIC_TITLE_MARKERS = [
  'official audio',
  'official video',
  'music video',
  'lyric video',
  'lyrics',
  'visualizer',
  'visualiser',
  'remix',
  'cover',
  'instrumental',
  'live session',
  'live performance',
  'single',
  'album track',
  'feat.',
  ' ft.',
];
const MUSIC_CHANNEL_MARKERS = [
  'records',
  'music',
  'vevo',
  'topic',
  'beats',
  'orchestra',
  'choir',
  'band',
  'artist',
];
const NON_MUSIC_MARKERS = [
  'trailer',
  'review',
  'documentary',
  'tutorial',
  'interview',
  'podcast',
  'news',
  'update',
  'walkthrough',
  'gameplay',
  'reaction',
];
const TAXONOMY_HINT_MARKERS: Record<string, readonly string[]> = {
  news: ['breaking', 'news', 'alert', 'live', 'bulletin', 'officials', 'report', 'update', 'transfer', 'injury'],
  commentary: [
    'commentary',
    'analysis',
    'opinion',
    'reaction',
    'breakdown',
    'editorial',
    'review',
    'comparison',
    'tutorial',
    'how to',
    'how-to',
    'hands on',
    'hands-on',
  ],
  documentary: [
    'documentary',
    'explainer',
    'history',
    'investigation',
    'deep dive',
    'episode',
    'lecture',
    'lesson',
    'course',
    'case study',
  ],
  music: MUSIC_TITLE_MARKERS,
  art: ['art', 'artwork', 'gallery', 'painting', 'illustration', 'concept art', 'exhibition'],
  satire: ['satire', 'parody', 'spoof', 'sketch', 'meme', 'comedy'],
  gaming: ['gameplay', 'gaming', 'walkthrough', "let's play", 'speedrun', 'build guide'],
  promo: ['trailer', 'teaser', 'promo', 'preorder', 'sale', 'discount', 'launch trailer', 'official trailer', 'reveal trailer', 'sponsored'],
};
let rescoreTimer: number | null = null;
const BATCH_SIZE = 12;
const MAX_PENDING_CARDS_PER_PASS = 36;
const BACKLOG_SCORE_DELAY_MS = 180;
let channelTrustProfiles: Record<string, FeedbackChannelProfile> = {};
let homepageStartupRetryCount = 0;
let homepageStartupRetryTimer: number | null = null;
let feedRerankEnabled = DEFAULT_FEED_RERANK_ENABLED;
let isApplyingFeedRerank = false;
let rerankMutationWindowTimer: number | null = null;
let channelTrustProfilesRefreshPromise: Promise<void> | null = null;
let backlogScoreTimer: number | null = null;
const OBSERVATION_SESSION_ID = createClientId('obs-session');
const HOMEPAGE_LOG_PREFIX = '[truthlens:homepage]';

type PendingCard = {
  card: HTMLElement;
  itemId: string;
  title: string;
  channelName: string;
  channelUrl: string | null;
  linkUrl: string | null;
  thumbnailRef: string | null;
  descriptionSnapshot: string | null;
  transcriptExcerpt: string | null;
  signature: string;
  rerankLocked: boolean;
  request: ScoreItemRequest;
};

type ManualReportMessage = {
  type: 'TRUTHLENS_OPEN_MANUAL_REPORT';
  linkUrl?: string | null;
  srcUrl?: string | null;
  pageUrl?: string | null;
  workflowMode?: ManualReportWorkflowMode;
};

type ExecutePageReportMessage = {
  type: 'TRUTHLENS_EXECUTE_PAGE_REPORT';
  target: ManualReportTarget;
  issueTypes: ManualReportIssueType[];
};

type PageReportMessage = ManualReportMessage | ExecutePageReportMessage;

function describeRuntimeError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return String(error);
}

function logHomepageDebug(message: string, payload?: Record<string, unknown>): void {
  if (payload) {
    console.debug(`${HOMEPAGE_LOG_PREFIX} ${message}`, payload);
    return;
  }
  console.debug(`${HOMEPAGE_LOG_PREFIX} ${message}`);
}

function logHomepageWarn(message: string, payload?: Record<string, unknown>): void {
  if (payload) {
    console.warn(`${HOMEPAGE_LOG_PREFIX} ${message}`, payload);
    return;
  }
  console.warn(`${HOMEPAGE_LOG_PREFIX} ${message}`);
}

function createClientId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function mountOverlay() {
  if (document.getElementById(OVERLAY_ID)) {
    return;
  }

  const rootNode = document.createElement('div');
  rootNode.id = OVERLAY_ID;
  document.body.appendChild(rootNode);
  createRoot(rootNode).render(<App />);
}

function extractText(card: HTMLElement, selector: string): string | null {
  return card.querySelector(selector)?.textContent?.trim() || null;
}

function extractAttribute(card: HTMLElement, selector: string, attribute: string): string | null {
  const value = card.querySelector<HTMLElement>(selector)?.getAttribute(attribute)?.trim();
  return value || null;
}

function firstNonEmpty(...values: Array<string | null | undefined>): string | null {
  return (
    values.find((value) => value !== null && value !== undefined && value.trim().length > 0) ??
    null
  );
}

function titleFromAriaLabel(label: string | null): string | null {
  if (!label) {
    return null;
  }

  const normalized = label.trim().replace(/\s+/g, ' ');
  const separatorMatch = normalized.match(/\s(?:by|af)\s/i);
  if (!separatorMatch || separatorMatch.index === undefined || separatorMatch.index <= 0) {
    return normalized;
  }
  return normalized.slice(0, separatorMatch.index).trim() || normalized;
}

function channelNameFromAriaLabel(label: string | null, title: string): string | null {
  if (!label) {
    return null;
  }

  const normalized = label.trim().replace(/\s+/g, ' ');
  const normalizedTitle = title.trim().replace(/\s+/g, ' ').toLowerCase();
  const searchStart = normalized.toLowerCase().startsWith(normalizedTitle)
    ? title.trim().replace(/\s+/g, ' ').length
    : 0;
  const tail = normalized.slice(searchStart);
  const markerMatch = tail.match(/\s(?:by|af)\s+(.+)$/i);
  if (!markerMatch) {
    return null;
  }

  return (
    markerMatch[1]
      .replace(/\s+\d[\d.,]*\s*(views?|visninger|subscribers?|abonnenter)\b.*$/i, '')
      .replace(
        /\s+\d+\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?|sekunder|minutter|timer|dage|uger|maaneder|ar)\b.*$/i,
        '',
      )
      .replace(/\s+for\s+\d+.*$/i, '')
      .trim() || null
  );
}

function extractVideoAriaLabel(card: HTMLElement): string | null {
  return firstNonEmpty(
    extractAttribute(card, 'a#video-title-link[aria-label]', 'aria-label'),
    extractAttribute(card, '#video-title[aria-label]', 'aria-label'),
    extractAttribute(card, 'a#thumbnail[aria-label]', 'aria-label'),
    extractAttribute(card, 'a[href*="watch"][aria-label]', 'aria-label'),
  );
}

function extractCardTitle(card: HTMLElement, index: number): string {
  const ariaLabel = extractVideoAriaLabel(card);
  return (
    firstNonEmpty(
      extractText(card, '#video-title, h3, a[title]'),
      extractAttribute(card, '#video-title[title]', 'title'),
      extractAttribute(card, 'a#video-title-link[title]', 'title'),
      extractAttribute(card, 'a[href*="watch"][title]', 'title'),
      titleFromAriaLabel(ariaLabel),
    ) ?? `Untitled item ${index + 1}`
  );
}

function buildItemId(card: HTMLElement, index: number): string {
  const existingItemId = card.getAttribute(ITEM_ID);
  if (existingItemId) {
    return existingItemId;
  }
  const href =
    card.querySelector<HTMLAnchorElement>(
      'a#thumbnail, a[href*="watch"], a[href*="/shorts/"], a[href*="playlist?list="]',
    )?.href || '';
  if (href) {
    return href;
  }
  return `card-${index + 1}`;
}

function matchesFeedCardSelector(element: Element): element is HTMLElement {
  return element instanceof HTMLElement && element.matches(CARD_SELECTOR);
}

function parseDurationSeconds(rawText: string | null): number | null {
  if (!rawText) {
    return null;
  }

  const parts = rawText
    .trim()
    .split(':')
    .map((part) => Number(part.replace(/[^\d]/g, '')))
    .filter((part) => Number.isFinite(part));
  if (parts.length < 2 || parts.length > 3) {
    return null;
  }

  if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  return parts[0] * 3600 + parts[1] * 60 + parts[2];
}

function parseLocalizedInteger(rawText: string | null): number | null {
  if (!rawText) {
    return null;
  }

  const normalized = rawText.trim().toLowerCase();
  const numberMatch = normalized.match(/(\d+(?:[.,]\d+)?)/);
  if (!numberMatch) {
    return null;
  }
  const numericValue = Number(numberMatch[1].replace(',', '.'));
  if (!Number.isFinite(numericValue)) {
    return null;
  }

  let multiplier = 1;
  if (/\b(k|tusind)\b/.test(normalized)) {
    multiplier = 1_000;
  } else if (/\b(m|mn|mio|million)\b/.test(normalized)) {
    multiplier = 1_000_000;
  } else if (/\b(b|mia|billion)\b/.test(normalized)) {
    multiplier = 1_000_000_000;
  }

  return Math.round(numericValue * multiplier);
}

function normalizeChannelKey(channelName: string): string {
  return channelName.trim().toLowerCase();
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function countPhraseHits(text: string, phrases: readonly string[]): number {
  const normalized = text.toLowerCase();
  return phrases.reduce((count, phrase) => count + (normalized.includes(phrase) ? 1 : 0), 0);
}

function isUnknownChannelName(channelName: string | null | undefined): boolean {
  return !channelName || normalizeChannelKey(channelName) === UNKNOWN_CHANNEL_NAME.toLowerCase();
}

function estimateTaxonomyHints(
  title: string,
  channelName: string,
  descriptionSnapshot: string | null,
): Record<string, number> {
  const normalizedTitle = title.toLowerCase();
  const normalizedChannel = channelName.toLowerCase();
  const normalizedDescription = (descriptionSnapshot ?? '').toLowerCase();
  const combined = [normalizedTitle, normalizedChannel, normalizedDescription].join(' ');
  const titleHits = countPhraseHits(normalizedTitle, MUSIC_TITLE_MARKERS);
  const channelHits = countPhraseHits(normalizedChannel, MUSIC_CHANNEL_MARKERS);
  const descriptionHits = countPhraseHits(normalizedDescription, MUSIC_TITLE_MARKERS);
  const nonMusicHits = countPhraseHits(combined, NON_MUSIC_MARKERS);
  const musicLikelihood = clamp(
    titleHits * 0.42 + channelHits * 0.2 + descriptionHits * 0.14 - nonMusicHits * 0.18,
    0,
    1,
  );
  const taxonomyHints = Object.fromEntries(
    Object.entries(TAXONOMY_HINT_MARKERS).map(([contentClass, markers]) => {
      const titleSignal = countPhraseHits(normalizedTitle, markers);
      const channelSignal = countPhraseHits(normalizedChannel, markers);
      const descriptionSignal = countPhraseHits(normalizedDescription, markers);
      const hintScore = clamp(
        titleSignal * 0.24 + channelSignal * 0.1 + descriptionSignal * 0.12,
        0,
        1,
      );
      return [`taxonomy_hint_${contentClass}`, Number(hintScore.toFixed(4))];
    }),
  ) as Record<string, number>;
  const strongestHint = Math.max(0, ...Object.values(taxonomyHints));

  return {
    music_likelihood: Number(musicLikelihood.toFixed(4)),
    title_music_signal: Number(clamp(titleHits / 2, 0, 1).toFixed(4)),
    channel_music_signal: Number(clamp((channelHits + descriptionHits) / 3, 0, 1).toFixed(4)),
    ...taxonomyHints,
    taxonomy_hint_unknown: Number(clamp(1 - strongestHint, 0, 1).toFixed(4)),
  };
}

function getChannelProfile(channelName: string): FeedbackChannelProfile | undefined {
  if (isUnknownChannelName(channelName)) {
    return undefined;
  }
  return channelTrustProfiles[normalizeChannelKey(channelName)];
}

function deriveChannelNameFromUrl(channelUrl: string | null): string | null {
  if (!channelUrl) {
    return null;
  }

  try {
    const url = new URL(channelUrl, window.location.href);
    const path = url.pathname.replace(/\/+$/, '');
    const segments = path.split('/').filter(Boolean);
    const lastSegment = segments.at(-1) ?? '';
    if (!lastSegment) {
      return null;
    }
    if (lastSegment.startsWith('@')) {
      return lastSegment.slice(1);
    }
    if (segments.length >= 2 && ['channel', 'c', 'user'].includes(segments[0])) {
      return lastSegment;
    }
    return null;
  } catch {
    return null;
  }
}

function extractChannelAnchor(card: HTMLElement): HTMLAnchorElement | null {
  const candidates = Array.from(
    card.querySelectorAll<HTMLAnchorElement>(
      [
        'ytd-channel-name a',
        '#channel-name a',
        '[id="channel-info"] a',
        'yt-formatted-string.ytd-channel-name a',
        'a[href^="/@"]',
        'a[href^="/channel/"]',
        'a[href^="/c/"]',
        'a[href^="/user/"]',
      ].join(', '),
    ),
  );

  return (
    candidates.find((anchor) => {
      const href = anchor.getAttribute('href') ?? '';
      return (
        !href.includes('/watch') &&
        !href.includes('/shorts/') &&
        (href.startsWith('/@') ||
          href.startsWith('/channel/') ||
          href.startsWith('/c/') ||
          href.startsWith('/user/'))
      );
    }) ?? null
  );
}

function extractChannelIdentity(
  card: HTMLElement,
  title: string,
): { channelName: string; channelUrl: string | null } {
  const channelAnchor = extractChannelAnchor(card);
  const channelUrl = channelAnchor?.href ?? null;
  const anchorText = channelAnchor?.textContent?.trim() ?? null;
  const selectorText =
    extractText(
      card,
      [
        'ytd-channel-name a',
        'ytd-channel-name',
        '#channel-name a',
        '#channel-name',
        '[id="channel-info"] a',
        '[id="channel-info"]',
        '#text.ytd-channel-name',
      ].join(', '),
    ) ?? null;
  const derivedName = deriveChannelNameFromUrl(channelUrl);
  const ariaName = channelNameFromAriaLabel(extractVideoAriaLabel(card), title);
  return {
    channelName: anchorText || selectorText || derivedName || ariaName || UNKNOWN_CHANNEL_NAME,
    channelUrl,
  };
}

async function refreshChannelTrustProfiles(): Promise<void> {
  if (channelTrustProfilesRefreshPromise) {
    return channelTrustProfilesRefreshPromise;
  }

  channelTrustProfilesRefreshPromise = (async () => {
    try {
      const summary = await fetchFeedbackSummary();
      if (summary.channel_profiles !== undefined) {
        channelTrustProfiles = summary.channel_profiles;
        await persistCachedChannelTrustProfiles(channelTrustProfiles);
      }
    } catch {
      // Fail soft and keep the previous trust snapshot.
    } finally {
      channelTrustProfilesRefreshPromise = null;
    }
  })();

  return channelTrustProfilesRefreshPromise;
}

function ensureOriginalIndex(card: HTMLElement, index: number): number {
  const existing = card.getAttribute(ORIGINAL_INDEX);
  if (existing !== null) {
    const parsed = Number(existing);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  card.setAttribute(ORIGINAL_INDEX, String(index));
  return index;
}

function normalizeComparableUrl(value: string | null): string | null {
  if (!value) {
    return null;
  }

  try {
    const url = new URL(value, window.location.href);
    if (url.pathname === '/watch') {
      const videoId = url.searchParams.get('v');
      const listId = url.searchParams.get('list');
      if (!videoId) {
        return url.pathname;
      }
      return listId ? `/watch?v=${videoId}&list=${listId}` : `/watch?v=${videoId}`;
    }
    if (url.pathname.startsWith('/shorts/')) {
      return url.pathname;
    }
    if (url.pathname === '/playlist') {
      const listId = url.searchParams.get('list');
      return listId ? `/playlist?list=${listId}` : url.pathname;
    }
    return url.toString();
  } catch {
    return value;
  }
}

function normalizeAssetUrl(value: string | null): string | null {
  if (!value) {
    return null;
  }

  try {
    const url = new URL(value, window.location.href);
    url.search = '';
    return url.toString();
  } catch {
    return value;
  }
}

function inferLinkKind(linkUrl: string | null): 'watch' | 'shorts' | 'other' | 'unknown' {
  if (!linkUrl) {
    return 'unknown';
  }
  try {
    const url = new URL(linkUrl, window.location.href);
    if (url.pathname === '/watch') {
      return 'watch';
    }
    if (url.pathname.startsWith('/shorts/')) {
      return 'shorts';
    }
    return 'other';
  } catch {
    return 'unknown';
  }
}

function parseCollectionIdentity(
  linkUrl: string | null,
): { scopeType: 'single' | 'mix' | 'playlist'; scopeId: string | null } {
  if (!linkUrl) {
    return { scopeType: 'single', scopeId: null };
  }
  try {
    const url = new URL(linkUrl, window.location.href);
    const listId = url.searchParams.get('list');
    if (!listId) {
      return { scopeType: 'single', scopeId: null };
    }
    return {
      scopeType: listId.startsWith('RD') ? 'mix' : 'playlist',
      scopeId: listId,
    };
  } catch {
    return { scopeType: 'single', scopeId: null };
  }
}

function collectionTitleFromCard(card: HTMLElement): string | null {
  const selectors = [
    '#video-title',
    'a[title]',
    'yt-formatted-string#text',
    'h3',
    '#header-description',
    '#subtitle',
  ];
  for (const selector of selectors) {
    const value = card.querySelector<HTMLElement>(selector)?.textContent?.trim();
    if (value) {
      return value;
    }
  }
  return null;
}

function extractCardContext(card: HTMLElement, index: number): PendingCard | null {
  ensureOriginalIndex(card, index);
  const title = extractCardTitle(card, index);
  const { channelName, channelUrl } = extractChannelIdentity(card, title);
  const thumbnailRef = card.querySelector<HTMLImageElement>('img')?.getAttribute('src') || null;
  const descriptionSnapshot = extractText(card, '#description-text, #metadata-line, .metadata-snippet');
  const transcriptExcerpt = null;
  const linkUrl =
    card.querySelector<HTMLAnchorElement>(
      'a#thumbnail, a[href*="watch"], a[href*="/shorts/"], a[href*="playlist?list="]',
    )
      ?.href || null;
  const linkKind = inferLinkKind(linkUrl);
  const durationSeconds = parseDurationSeconds(
    extractText(
      card,
      'ytd-thumbnail-overlay-time-status-renderer span, .ytd-thumbnail-overlay-time-status-renderer, .badge-shape-wiz__text',
    ),
  );
  const metadataLineSpans = Array.from(card.querySelectorAll<HTMLElement>('#metadata-line span'));
  const viewCount =
    parseLocalizedInteger(metadataLineSpans[0]?.textContent ?? null) ??
    parseLocalizedInteger(descriptionSnapshot);
  const uploadTime = metadataLineSpans[1]?.textContent?.trim() || null;
  const itemId = buildItemId(card, index);
  const signature = buildStableFeedCardSignature({
    itemId,
    title,
    channelName,
    linkUrl,
  });
  const taxonomyHints = estimateTaxonomyHints(title, channelName, descriptionSnapshot);
  const historyFeatures = buildChannelHistoryFeatures(getChannelProfile(channelName), taxonomyHints);
  const profile = getChannelProfile(channelName);
  return {
    card,
    itemId,
    title,
    channelName,
    channelUrl,
    linkUrl,
    thumbnailRef,
    descriptionSnapshot,
    transcriptExcerpt,
    signature,
    rerankLocked: isSponsoredCard(card, linkKind),
    request: {
      item_id: itemId,
      title,
      thumbnail_ref: thumbnailRef,
      description_snapshot: descriptionSnapshot,
      transcript_excerpt: transcriptExcerpt,
      channel: {
        channel_name: channelName,
        channel_url: channelUrl,
        prior_flags: priorFlagsFromProfile(profile),
        channel_history_features: historyFeatures,
      },
      metadata: {
        duration_seconds: durationSeconds,
        view_count: viewCount,
        upload_time: uploadTime,
      },
      user_context: buildUserContext(),
      runtime_context: {
        surface: 'extension-feed',
        review_requested: false,
        source_provenance: window.location.pathname,
      },
    },
  };
}

function resolveCollectionMembers(
  sourceEntry: PendingCard,
): { collectionScope: ManualReviewCollectionScope | null; resolvedMembers: ManualReviewCollectionMember[] } {
  const { scopeType, scopeId } = parseCollectionIdentity(sourceEntry.linkUrl);
  if (!scopeId) {
    return { collectionScope: null, resolvedMembers: [] };
  }

  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const cards = Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')));
  const membersById = new Map<string, ManualReviewCollectionMember>();

  cards.forEach((card, index) => {
    const entry = extractCardContext(card, index);
    if (!entry) {
      return;
    }
    const identity = parseCollectionIdentity(entry.linkUrl);
    if (identity.scopeId !== scopeId) {
      return;
    }
    membersById.set(entry.itemId, {
      item_id: entry.itemId,
      title_snapshot: entry.title,
      channel_name: isUnknownChannelName(entry.channelName) ? null : entry.channelName,
      link_url: entry.linkUrl,
      thumbnail_ref: entry.thumbnailRef,
      resolved: Boolean(entry.linkUrl),
    });
  });

  if (!membersById.has(sourceEntry.itemId)) {
    membersById.set(sourceEntry.itemId, {
      item_id: sourceEntry.itemId,
      title_snapshot: sourceEntry.title,
      channel_name: isUnknownChannelName(sourceEntry.channelName) ? null : sourceEntry.channelName,
      link_url: sourceEntry.linkUrl,
      thumbnail_ref: sourceEntry.thumbnailRef,
      resolved: Boolean(sourceEntry.linkUrl),
    });
  }

  const resolvedMembers = Array.from(membersById.values());
  const resolvedMemberCount = resolvedMembers.filter((member) => member.resolved && member.link_url).length;
  const unresolvedMemberCount = resolvedMembers.length - resolvedMemberCount;

  return {
    resolvedMembers,
    collectionScope: {
      scope_type: scopeType,
      scope_id: scopeId,
      collection_title: collectionTitleFromCard(sourceEntry.card) ?? sourceEntry.title,
      source_item_id: sourceEntry.itemId,
      source_link_url: sourceEntry.linkUrl,
      trigger_origin: 'single-item',
      apply_to_all: false,
      resolved_member_count: resolvedMemberCount,
      unresolved_member_count: unresolvedMemberCount,
      member_items: resolvedMembers,
    },
  };
}

function buildManualReportTarget(
  entry: PendingCard,
  score: ScoreResult | null,
  workflowMode: ManualReportWorkflowMode,
): ManualReportTarget {
  const { collectionScope } = resolveCollectionMembers(entry);
  const profile = getChannelProfile(entry.channelName);
  return {
    itemId: entry.itemId,
    workflowMode,
    title: entry.title,
    channelName: entry.channelName,
    channelUrl: entry.channelUrl,
    linkUrl: entry.linkUrl,
    thumbnailRef: entry.thumbnailRef,
    descriptionSnapshot: entry.descriptionSnapshot,
    transcriptExcerpt: entry.transcriptExcerpt,
    collectionScope,
    channelReportCount: priorFlagsFromProfile(profile),
    score,
  };
}

function openManualReport(entry: PendingCard, score: ScoreResult | null) {
  useOverlayStore.getState().openManualReport(buildManualReportTarget(entry, score, 'report'));
}

function openManualReview(entry: PendingCard, score: ScoreResult | null, workflowMode: ManualReportWorkflowMode) {
  useOverlayStore.getState().openManualReport(buildManualReportTarget(entry, score, workflowMode));
}

function isSuppressedFeedCard(card: HTMLElement): boolean {
  return (
    card.getAttribute(SUPPRESSED) !== null ||
    card.classList.contains('truthlens-card-hidden') ||
    card.classList.contains('truthlens-card-suppressed')
  );
}

function clearCardAugmentations(card: HTMLElement) {
  card.classList.remove('truthlens-card-hidden');
  card.classList.remove('truthlens-card-suppressed');
  card.classList.remove('truthlens-card-blur');
  card.classList.remove('truthlens-card-boosted');
  card.classList.remove('truthlens-card-steady');
  card.classList.remove('truthlens-card-downranked');
  card.removeAttribute(SUPPRESSED);
  card.removeAttribute('aria-hidden');
  card.querySelector('.truthlens-card-flag')?.remove();
  card.querySelector('.truthlens-review-prompt')?.remove();
  card.querySelector('.truthlens-action-row')?.remove();
  card.querySelector('.truthlens-details')?.remove();
}

function syncPersonalizationPresentation(
  card: HTMLElement,
  score: ScoreResult,
  personalization: PersonalizationSnapshot,
  presentation: FeedPresentationSnapshot,
): void {
  const shouldShowFlag = shouldShowPersonalizationBadge(personalization, score);
  const truthScoreLabel = presentation.truthScore.toFixed(1);
  const feedRiskLabel = presentation.feedRiskScore.toFixed(1);
  const runtimeLabel = presentation.runtimeRiskScore.toFixed(1);
  const historyAdjustmentLabel = presentation.historyAdjustmentScore.toFixed(1);
  const rerankPriorityLabel = presentation.rerankPriority.toFixed(1);
  card.classList.remove('truthlens-card-boosted');
  card.classList.remove('truthlens-card-steady');
  card.classList.remove('truthlens-card-downranked');
  card.classList.add(`truthlens-card-${personalization.bucket}`);
  card.setAttribute(PERSONALIZATION, personalization.bucket);
  card.setAttribute(PERSONALIZATION_SCORE, personalization.rankingScore.toFixed(2));
  card.setAttribute(TRUTH_SCORE, truthScoreLabel);
  card.setAttribute(FEED_RISK_SCORE, feedRiskLabel);
  card.setAttribute(RUNTIME_SCORE, runtimeLabel);
  card.setAttribute(TRUTH_BAND, presentation.truthBand);
  card.setAttribute(RERANK_PRIORITY, rerankPriorityLabel);
  card.setAttribute(RERANK_LOCKED, presentation.rerankLocked ? 'true' : 'false');
  card.setAttribute(
    'data-truthlens-personalization-reasons',
    `Truth score ${truthScoreLabel}/10. Internal feed risk ${feedRiskLabel}/10. Raw runtime risk ${runtimeLabel}/10. Channel-history adjustment ${historyAdjustmentLabel}/10. Local rerank priority ${rerankPriorityLabel}/10. Local personalization rank ${personalization.rankingScore.toFixed(1)}/10. Channel trust ${personalization.trustScore.toFixed(1)}/10: ${personalization.reasons.join('; ')}`,
  );

  const existingFlag = card.querySelector<HTMLElement>('.truthlens-card-flag');
  if (!shouldShowFlag) {
    existingFlag?.remove();
    return;
  }

  const flag = existingFlag ?? document.createElement('span');
  flag.className = `truthlens-card-flag truthlens-card-flag-${presentation.truthBand} truthlens-card-flag-${personalization.bucket}`;
  flag.textContent = truthScoreLabel;
  flag.title = `TruthLens truth score ${truthScoreLabel}/10. Internal feed risk ${feedRiskLabel}/10. Raw runtime risk ${runtimeLabel}/10. Channel-history adjustment ${historyAdjustmentLabel}/10. Local rerank priority ${rerankPriorityLabel}/10. Recommended action ${score.recommended_action}. Local personalization rank ${personalization.rankingScore.toFixed(1)}/10. Channel trust ${personalization.trustScore.toFixed(1)}/10. ${personalization.reasons.join('; ')}.`;
  if (!existingFlag) {
    card.appendChild(flag);
  }
}

function beginFeedRerankMutationWindow(): void {
  isApplyingFeedRerank = true;
  if (rerankMutationWindowTimer !== null) {
    window.clearTimeout(rerankMutationWindowTimer);
  }
  rerankMutationWindowTimer = window.setTimeout(() => {
    rerankMutationWindowTimer = null;
    isApplyingFeedRerank = false;
  }, 0);
}

function directCardChildren(container: HTMLElement): HTMLElement[] {
  return Array.from(container.children).filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement &&
      matchesFeedCardSelector(child) &&
      !isSuppressedFeedCard(child),
  );
}

function readRerankChunkId(card: HTMLElement): number | null {
  const attributeValue = card.getAttribute(RERANK_CHUNK_ID);
  if (attributeValue === null) {
    return null;
  }
  const value = Number(attributeValue);
  if (!Number.isInteger(value) || value < 0) {
    return null;
  }
  return value;
}

function clearRerankChunkState(card: HTMLElement): void {
  card.removeAttribute(RERANK_CHUNK_ID);
  card.removeAttribute(RERANK_CHUNK_SEALED);
}

function markRerankChunk(card: HTMLElement, chunkId: number): void {
  card.setAttribute(RERANK_CHUNK_ID, String(chunkId));
  card.setAttribute(RERANK_CHUNK_SEALED, 'true');
}

function isSealedRerankChunk(card: HTMLElement): boolean {
  return (
    card.getAttribute(RERANK_CHUNK_SEALED) === 'true' &&
    readRerankChunkId(card) !== null
  );
}

function nextRerankChunkId(cardsInContainer: HTMLElement[]): number {
  return cardsInContainer.reduce((maxChunkId, card) => {
    const chunkId = readRerankChunkId(card);
    return chunkId === null ? maxChunkId : Math.max(maxChunkId, chunkId);
  }, -1) + 1;
}

function resolveRerankContainer(card: HTMLElement): HTMLElement | null {
  let current = card.parentElement;
  while (current) {
    const directCards = directCardChildren(current);
    if (directCards.length >= 2 && directCards.includes(card)) {
      return current;
    }
    current = current.parentElement;
  }
  return card.parentElement;
}

function reorderCardsWithinContainer(
  container: HTMLElement,
  orderedCards: HTMLElement[],
): void {
  const currentCards = directCardChildren(container);
  if (
    currentCards.length !== orderedCards.length ||
    currentCards.every((card, index) => card === orderedCards[index])
  ) {
    return;
  }

  beginFeedRerankMutationWindow();
  const startAnchor = document.createComment('truthlens-rerank-start');
  container.insertBefore(startAnchor, currentCards[0]);
  const fragment = document.createDocumentFragment();
  orderedCards.forEach((card) => {
    fragment.appendChild(card);
  });
  container.insertBefore(fragment, startAnchor.nextSibling);
  startAnchor.remove();
}

function restoreOriginalFeedOrdering(): void {
  const cards = Array.from(document.querySelectorAll<HTMLElement>(CARD_SELECTOR)).filter(
    (card) => !isSuppressedFeedCard(card),
  );
  const containers = new Map<HTMLElement, HTMLElement[]>();

  cards.forEach((card) => {
    clearRerankChunkState(card);
    const container = resolveRerankContainer(card);
    if (!container) {
      return;
    }
    const group = containers.get(container) ?? [];
    group.push(card);
    containers.set(container, group);
  });

  containers.forEach((cardsInContainer, container) => {
    const orderedCards = [...cardsInContainer].sort((left, right) => {
      return ensureOriginalIndex(left, 0) - ensureOriginalIndex(right, 0);
    });
    reorderCardsWithinContainer(container, orderedCards);
  });
}

function applyLocalPersonalizationOrdering(targetCards?: HTMLElement[]) {
  if (!feedRerankEnabled) {
    restoreOriginalFeedOrdering();
    return;
  }

  const cards =
    targetCards && targetCards.length > 0
      ? targetCards.filter((card) => !isSuppressedFeedCard(card))
      : Array.from(document.querySelectorAll<HTMLElement>(CARD_SELECTOR)).filter(
          (card) => !isSuppressedFeedCard(card),
        );
  const containers = new Map<HTMLElement, HTMLElement[]>();

  cards.forEach((card, index) => {
    ensureOriginalIndex(card, index);
    const container = resolveRerankContainer(card);
    if (!container) {
      return;
    }
    const group = containers.get(container) ?? [];
    group.push(card);
    containers.set(container, group);
  });

  containers.forEach((_targetCardsInContainer, container) => {
    const cardsInContainer = directCardChildren(container);
    cardsInContainer.forEach((card, index) => {
      ensureOriginalIndex(card, index);
    });
    const chunkCards = cardsInContainer.filter(
      (card) => card.getAttribute(PROCESSED) === 'true' && readRerankChunkId(card) === null,
    );
    if (chunkCards.length === 0) {
      return;
    }

    const chunkId = nextRerankChunkId(cardsInContainer);
    const orderedChunkCards = planStableRerankOrder(
      chunkCards.map((card) => {
        const originalIndex = ensureOriginalIndex(card, 0);
        const rerankPriority = Number(card.getAttribute(RERANK_PRIORITY) ?? Number.NaN);
        const rerankLocked =
          card.getAttribute(RERANK_LOCKED) === 'true' || !Number.isFinite(rerankPriority);
        const truthBand = (card.getAttribute(TRUTH_BAND) as TruthBand | null) ?? 'yellow';
        return {
          card,
          originalIndex,
          rerankPriority: Number.isFinite(rerankPriority) ? rerankPriority : 0,
          rerankLocked,
          truthBand,
        };
      }),
    );
    const chunkSet = new Set(chunkCards);
    const orderedChunkSet = new Set(orderedChunkCards);
    const sealedCards = cardsInContainer.filter(
      (card) => !chunkSet.has(card) && isSealedRerankChunk(card),
    );
    const remainingCards = cardsInContainer.filter(
      (card) => !sealedCards.includes(card) && !orderedChunkSet.has(card),
    );

    reorderCardsWithinContainer(container, [
      ...sealedCards,
      ...orderedChunkCards,
      ...remainingCards,
    ]);
    orderedChunkCards.forEach((card) => {
      markRerankChunk(card, chunkId);
    });
  });
}

function suppressCardFromFeed(card: HTMLElement, reason: string): void {
  const container = resolveRerankContainer(card);
  card.classList.add('truthlens-card-hidden', 'truthlens-card-suppressed');
  card.setAttribute(SUPPRESSED, reason);
  card.setAttribute('aria-hidden', 'true');
  card.removeAttribute(PROCESSING);
  clearRerankChunkState(card);

  const visibleSiblings = container ? directCardChildren(container) : [];
  visibleSiblings.forEach(clearRerankChunkState);
  applyLocalPersonalizationOrdering(visibleSiblings);
}

function createFeedbackPayload(
  itemId: string,
  channelName: string | null,
  actionShown: 'none' | 'badge' | 'blur' | 'hide' | 'ask-report',
  userAction: string,
  beforeScore: number,
  explanationId: string | null,
  observationId: string | null,
  artifactProvenance: ScoreResult['artifact_provenance'],
  afterScore = beforeScore,
) {
  return {
    feedback_id: createClientId('feedback'),
    item_id: itemId,
    item_hash: null,
    observation_id: observationId,
    channel_name: isUnknownChannelName(channelName) ? null : channelName,
    model_version: 'extension-runtime',
    policy_version: 'adaptive-threshold-v1',
    action_shown: actionShown,
    user_action: userAction,
    explanation_id: explanationId,
    before_score: beforeScore,
    after_score: afterScore,
    timestamp: new Date().toISOString(),
    runtime_context: {
      surface: 'extension-feed',
      review_requested: false,
      source_provenance: window.location.pathname,
    },
    artifact_provenance: artifactProvenance,
  } as const;
}

function buildBrowserObservationRecord(
  entry: PendingCard,
  score: ScoreResult,
): BrowserObservationRecord {
  const originalIndex = Number(entry.card.getAttribute(ORIGINAL_INDEX));
  const { collectionScope } = resolveCollectionMembers(entry);
  return {
    observation_id: createClientId('observation'),
    item_id: entry.itemId,
    item_hash: entry.signature,
    title_snapshot: entry.title,
    channel_name: isUnknownChannelName(entry.channelName) ? null : entry.channelName,
    channel_url: entry.channelUrl,
    link_url: entry.linkUrl,
    thumbnail_ref: entry.thumbnailRef,
    description_snapshot: entry.descriptionSnapshot,
    transcript_excerpt: entry.transcriptExcerpt,
    metadata: entry.request.metadata,
    runtime_context: entry.request.runtime_context,
    distilled_features: {
      card_index: Number.isFinite(originalIndex) ? originalIndex : null,
      link_kind: inferLinkKind(entry.linkUrl),
      has_thumbnail: Boolean(entry.thumbnailRef),
      has_description_snapshot: Boolean(entry.descriptionSnapshot),
      has_transcript_excerpt: Boolean(entry.transcriptExcerpt),
      collection_scope_type: collectionScope?.scope_type ?? 'single',
      collection_member_count: collectionScope?.member_items.length ?? 1,
      collection_resolved_member_count: collectionScope?.resolved_member_count ?? 1,
      title_token_count: entry.title.trim().split(/\s+/).filter(Boolean).length,
      description_token_count: (entry.descriptionSnapshot ?? '').trim().split(/\s+/).filter(Boolean).length,
      channel_known: !isUnknownChannelName(entry.channelName),
      duration_seconds: entry.request.metadata.duration_seconds ?? null,
    },
    score_snapshot: {
      risk_score: score.risk_score,
      calibrated_score: score.calibrated_score,
      uncertainty: score.uncertainty,
      recommended_action: score.recommended_action,
      content_class: score.content_class,
      content_class_confidence: score.content_class_confidence,
      explanation_id: score.explanation_id,
    },
    provenance: {
      observed_at: new Date().toISOString(),
      collector: 'extension-dom',
      collector_version: 'extension-runtime',
      session_id: OBSERVATION_SESSION_ID,
      page_url: window.location.href,
      source_path: window.location.pathname,
    },
    collection_scope: collectionScope,
  };
}

function attachActions(
  entry: PendingCard,
  score: ScoreResult,
) {
  const { card, itemId, channelName } = entry;
  const actionRow = document.createElement('div');
  actionRow.className = 'truthlens-action-row';

  const whyButton = document.createElement('button');
  whyButton.className = 'truthlens-action-button';
  whyButton.textContent = 'Why';

  const safeButton = document.createElement('button');
  safeButton.className = 'truthlens-action-button';
  safeButton.textContent = 'Not misleading';

  const hideButton = document.createElement('button');
  hideButton.className = 'truthlens-action-button';
  hideButton.textContent = 'Hide';

  const muteButton = document.createElement('button');
  muteButton.className = 'truthlens-action-button';
  muteButton.textContent = 'Mute channel';

  const reportButton = document.createElement('button');
  reportButton.className = 'truthlens-action-button';
  reportButton.textContent = 'Report';

  const details = document.createElement('div');
  details.className = 'truthlens-details';
  details.hidden = true;
  const summary = document.createElement('p');
  summary.className = 'truthlens-details-summary';
  summary.textContent = score.explanation_summary || 'No explanation available for this item.';
  details.appendChild(summary);

  if (score.evidence.length > 0) {
    const evidenceList = document.createElement('ul');
    evidenceList.className = 'truthlens-evidence-list';
    for (const entry of score.evidence) {
      const listItem = document.createElement('li');
      const evidenceScore =
        typeof entry.score === 'number' ? ` (${Math.round(entry.score * 100)}%)` : '';
      listItem.textContent = `${entry.label}${evidenceScore}`;
      evidenceList.appendChild(listItem);
    }
    details.appendChild(evidenceList);
  } else if (score.reasons.length > 0) {
    const fallbackList = document.createElement('ul');
    fallbackList.className = 'truthlens-evidence-list';
    for (const reason of score.reasons) {
      const listItem = document.createElement('li');
      listItem.textContent = reason;
      fallbackList.appendChild(listItem);
    }
    details.appendChild(fallbackList);
  }

  if (score.explanation_id) {
    const idLabel = document.createElement('p');
    idLabel.className = 'truthlens-details-meta';
    idLabel.textContent = `Explanation ID: ${score.explanation_id}`;
    details.appendChild(idLabel);
  }
  const classLabel = document.createElement('p');
  classLabel.className = 'truthlens-details-meta';
  classLabel.textContent = `Class: ${score.content_class} (${Math.round(score.content_class_confidence * 100)}%)`;
  details.appendChild(classLabel);
  if (score.bias_profile.guardrail_applied) {
    const guardrailLabel = document.createElement('p');
    guardrailLabel.className = 'truthlens-details-meta';
    guardrailLabel.textContent = `Guardrail: ${score.bias_profile.guardrail_applied}`;
    details.appendChild(guardrailLabel);
  }
  if (score.bias_profile.negative_biases.length > 0) {
    const biasLabel = document.createElement('p');
    biasLabel.className = 'truthlens-details-meta';
    biasLabel.textContent = `Negative bias: ${score.bias_profile.negative_biases.join(', ')}`;
    details.appendChild(biasLabel);
  }

  whyButton.addEventListener('click', () => {
    details.hidden = !details.hidden;
  });

  safeButton.addEventListener('click', () => {
    void sendFeedbackEvent(
      createFeedbackPayload(
        itemId,
        channelName,
        score.recommended_action,
        'not-misleading',
        score.risk_score,
        score.explanation_id ?? null,
        card.getAttribute(OBSERVATION_ID),
        score.artifact_provenance,
      ),
    );
    card.classList.remove('truthlens-card-hidden');
    card.classList.remove('truthlens-card-blur');
  });

  hideButton.addEventListener('click', () => {
    suppressCardFromFeed(card, 'hide-locally');
    void sendFeedbackEvent(
      createFeedbackPayload(
        itemId,
        channelName,
        score.recommended_action,
        'hide-locally',
        score.risk_score,
        score.explanation_id ?? null,
        card.getAttribute(OBSERVATION_ID),
        score.artifact_provenance,
      ),
    );
  });

  muteButton.addEventListener('click', () => {
    if (isUnknownChannelName(channelName)) {
      return;
    }
    muteChannel(channelName);
    suppressCardFromFeed(card, 'mute-channel-local');
    void sendFeedbackEvent(
      createFeedbackPayload(
        itemId,
        channelName,
        score.recommended_action,
        'mute-channel-local',
        score.risk_score,
        score.explanation_id ?? null,
        card.getAttribute(OBSERVATION_ID),
        score.artifact_provenance,
      ),
    );
  });

  reportButton.addEventListener('click', () => {
    openManualReport(entry, score);
  });

  actionRow.append(whyButton, safeButton, hideButton, muteButton, reportButton);
  card.append(actionRow, details);
}

function buildPendingCard(card: HTMLElement, index: number): PendingCard | null {
  if (isSuppressedFeedCard(card)) {
    return null;
  }
  if (card.getAttribute(PROCESSING) === 'true') {
    return null;
  }

  const entry = extractCardContext(card, index);
  if (!entry) {
    return null;
  }
  const { title, channelName, itemId, signature } = entry;
  if (
    !isReadyForStableFeedScoring({
      itemId,
      title,
      channelName,
      linkUrl: entry.linkUrl,
    })
  ) {
    return null;
  }
  if (!isUnknownChannelName(channelName) && isChannelMuted(channelName)) {
    card.setAttribute(PROCESSED, 'true');
    card.setAttribute(
      SIGNATURE,
      buildStableFeedCardSignature({
        itemId,
        title,
        channelName,
        linkUrl: entry.linkUrl,
      }),
    );
    suppressCardFromFeed(card, 'muted-channel');
    return null;
  }
  if (
    card.getAttribute(PROCESSED) === 'true' &&
    card.getAttribute(SIGNATURE) === signature &&
    card.getAttribute(ITEM_ID) === itemId
  ) {
    return null;
  }
  card.removeAttribute(OBSERVATION_ID);
  card.setAttribute(PROCESSING, 'true');
  return entry;
}

function applyScoreToCard(pendingCard: PendingCard, score: ScoreResult) {
  const { card, itemId, signature } = pendingCard;
  useOverlayStore.getState().recordScore(itemId, score);
  clearCardAugmentations(card);
  const profile = getChannelProfile(pendingCard.channelName);
  const personalization = buildPersonalizationSnapshot(score, profile);
  const musicLikelihood = Number(
    pendingCard.request.channel.channel_history_features.music_likelihood ?? 0,
  );
  const reviewPrompt = inferReviewPromptDecision(score, musicLikelihood);
  const presentation = buildFeedPresentationSnapshot(
    score,
    personalization,
    profile,
    reviewPrompt,
    pendingCard.rerankLocked ||
      isUnknownChannelName(pendingCard.channelName),
  );

  syncPersonalizationPresentation(card, score, personalization, presentation);

  if (score.recommended_action === 'blur') {
    card.classList.add('truthlens-card-blur');
  }
  card.setAttribute('data-truthlens-review-mode', reviewPrompt.workflowMode);
  const reviewButton = document.createElement('button');
  reviewButton.type = 'button';
  reviewButton.className = `truthlens-review-prompt truthlens-review-prompt-${reviewPrompt.workflowMode}`;
  reviewButton.textContent = reviewPrompt.label;
  reviewButton.title = reviewPrompt.reason;
  reviewButton.addEventListener('click', () => {
    openManualReview(pendingCard, score, reviewPrompt.workflowMode);
  });
  card.appendChild(reviewButton);
  attachActions(pendingCard, score);
  card.setAttribute(PROCESSED, 'true');
  card.setAttribute(ITEM_ID, itemId);
  card.setAttribute(SIGNATURE, signature);
  if (!card.getAttribute(OBSERVATION_ID)) {
    const observation = buildBrowserObservationRecord(pendingCard, score);
    card.setAttribute(OBSERVATION_ID, observation.observation_id);
    void sendBrowserObservation(observation);
  }
  card.removeAttribute(PROCESSING);
}

function chunk<T>(items: T[], size: number): T[][] {
  const batches: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    batches.push(items.slice(index, index + size));
  }
  return batches;
}

function findManualReportTarget(message: ManualReportMessage): ManualReportTarget | null {
  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const normalizedLink = normalizeComparableUrl(message.linkUrl ?? null);
  const normalizedSrc = normalizeAssetUrl(message.srcUrl ?? null);
  const cards = Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')));

  for (let index = 0; index < cards.length; index += 1) {
    const entry = extractCardContext(cards[index], index);
    if (!entry) {
      continue;
    }
    const linkMatch =
      normalizedLink !== null && normalizeComparableUrl(entry.linkUrl) === normalizedLink;
    const imageMatch =
      normalizedSrc !== null && normalizeAssetUrl(entry.thumbnailRef) === normalizedSrc;
    if (linkMatch || imageMatch) {
      const score = useOverlayStore.getState().scoresByItemId[entry.itemId] ?? null;
      return buildManualReportTarget(entry, score, message.workflowMode ?? 'report');
    }
  }

  return null;
}

function matchesSubmittedReviewTarget(
  entry: PendingCard,
  target: ManualReviewSubmittedTarget,
): boolean {
  if (entry.itemId === target.itemId) {
    return true;
  }

  const linkMatch =
    target.linkUrl !== null &&
    normalizeComparableUrl(entry.linkUrl) === normalizeComparableUrl(target.linkUrl);
  const imageMatch =
    target.thumbnailRef !== null &&
    normalizeAssetUrl(entry.thumbnailRef) === normalizeAssetUrl(target.thumbnailRef);
  return linkMatch || imageMatch;
}

function findSubmittedReviewCard(
  target: ManualReviewSubmittedTarget,
): { card: HTMLElement; entry: PendingCard } | null {
  const cards = Array.from(document.querySelectorAll<HTMLElement>(CARD_SELECTOR));
  for (let index = 0; index < cards.length; index += 1) {
    const card = cards[index];
    const entry = extractCardContext(card, index);
    if (!entry || !matchesSubmittedReviewTarget(entry, target)) {
      continue;
    }
    return { card, entry };
  }
  return null;
}

function applyManualReviewSubmission(detail: ManualReviewSubmittedDetail): void {
  if (detail.workflowMode !== 'report') {
    return;
  }

  const touchedCards: HTMLElement[] = [];
  detail.targets.forEach((target) => {
    const resolved = findSubmittedReviewCard(target);
    if (!resolved) {
      return;
    }
    const score =
      useOverlayStore.getState().scoresByItemId[resolved.entry.itemId] ??
      useOverlayStore.getState().scoresByItemId[target.itemId] ??
      null;
    if (score) {
      const profile = getChannelProfile(resolved.entry.channelName);
      const adjustment = adjustScoreForReportedContent(
        score,
        detail.requestedOutcome,
        priorFlagsFromProfile(profile),
      );
      applyScoreToCard(resolved.entry, adjustment.adjustedScore);
    }
    suppressCardFromFeed(resolved.card, detail.userAction);
    touchedCards.push(resolved.card);
  });

  if (touchedCards.length > 0) {
    void refreshChannelTrustProfiles();
  }
}

function installManualReviewSubmissionListener(): void {
  registerManualReviewSubmittedHandler(applyManualReviewSubmission);
  window.addEventListener(MANUAL_REVIEW_SUBMITTED_EVENT, (event) => {
    applyManualReviewSubmission(
      (event as CustomEvent<ManualReviewSubmittedDetail>).detail,
    );
  });
}

function installRuntimeListeners() {
  if (typeof chrome === 'undefined' || !chrome.runtime?.onMessage) {
    return;
  }

  chrome.runtime.onMessage.addListener((message: PageReportMessage, _sender, sendResponse) => {
    if (message?.type === 'TRUTHLENS_OPEN_MANUAL_REPORT') {
      const target = findManualReportTarget(message);
      if (!target) {
        sendResponse({ ok: false });
        return;
      }

      useOverlayStore.getState().openManualReport(target);
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'TRUTHLENS_EXECUTE_PAGE_REPORT') {
      void submitYouTubePageReportInDocument(message.target, message.issueTypes)
        .then((result: YouTubePageReportResult) => {
          sendResponse({ ok: true, data: result });
        })
        .catch((error: unknown) => {
          sendResponse({
            ok: false,
            error:
              error instanceof Error
                ? error.message
                : 'TruthLens could not finish the protected YouTube report flow on the background tab.',
          });
        });
      return true;
    }
  });
}

function installFeedRerankSettingListener() {
  if (typeof chrome === 'undefined' || !chrome.storage?.onChanged) {
    return;
  }

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== 'local' || !(FEED_RERANK_ENABLED_KEY in changes)) {
      return;
    }
    const nextValue = changes[FEED_RERANK_ENABLED_KEY]?.newValue;
    feedRerankEnabled =
      typeof nextValue === 'boolean' ? nextValue : DEFAULT_FEED_RERANK_ENABLED;
    applyLocalPersonalizationOrdering();
  });
}

function scheduleBacklogScorePass(): void {
  if (backlogScoreTimer !== null) {
    return;
  }

  backlogScoreTimer = window.setTimeout(() => {
    backlogScoreTimer = null;
    requestScoreCards('mutation');
  }, BACKLOG_SCORE_DELAY_MS);
}

async function scoreCards(trigger: HomepageScoreTrigger = 'mutation') {
  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const cards = Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')));
  let preDispatchFailures = 0;

  logHomepageDebug('score pass started', {
    pathname: window.location.pathname,
    trigger,
  });
  logHomepageDebug('candidate cards discovered', {
    candidateCount: cards.length,
    trigger,
  });

  if (cards.length > 0) {
    void refreshChannelTrustProfiles();
  }

  const pendingCards = collectSafePendingEntries(cards, (card, index) => buildPendingCard(card, index), (error, card, index) => {
    preDispatchFailures += 1;
    card.removeAttribute(PROCESSING);
    logHomepageWarn('per-card context extraction failed', {
      cardIndex: index,
      reason: describeRuntimeError(error),
      trigger,
    });
  });

  logHomepageDebug('pending cards resolved', {
    pendingCount: pendingCards.length,
    preDispatchFailures,
    trigger,
  });

  if (preDispatchFailures > 0) {
    logHomepageWarn('scoring encountered pre-request failures', {
      pendingCount: pendingCards.length,
      preDispatchFailures,
      trigger,
    });
  }

  if (shouldScheduleHomepageStartupRetry(window.location.pathname, trigger, pendingCards.length, homepageStartupRetryCount)) {
    if (homepageStartupRetryTimer === null) {
      logHomepageDebug('scheduling one homepage startup retry', {
        delayMs: HOMEPAGE_STARTUP_RETRY_DELAY_MS,
      });
      homepageStartupRetryTimer = window.setTimeout(() => {
        homepageStartupRetryTimer = null;
        homepageStartupRetryCount += 1;
        requestScoreCards('homepage-retry');
      }, HOMEPAGE_STARTUP_RETRY_DELAY_MS);
    }
    if (pendingCards.length === 0) {
      return;
    }
  }

  const cardsForPass = pendingCards.slice(0, MAX_PENDING_CARDS_PER_PASS);
  const deferredCards = pendingCards.slice(MAX_PENDING_CARDS_PER_PASS);
  deferredCards.forEach((entry) => {
    entry.card.removeAttribute(PROCESSING);
  });
  if (deferredCards.length > 0) {
    logHomepageDebug('deferred pending cards to keep feed scoring responsive', {
      deferredCount: deferredCards.length,
      maxPendingCardsPerPass: MAX_PENDING_CARDS_PER_PASS,
      trigger,
    });
    scheduleBacklogScorePass();
  }

  for (const batch of chunk(cardsForPass, BATCH_SIZE)) {
    const scores = await batchScoreFeedItems(batch.map((entry) => entry.request));
    const scoredCards: HTMLElement[] = [];
    for (const entry of batch) {
      const score = scores[entry.itemId];
      if (score) {
        applyScoreToCard(entry, score);
        scoredCards.push(entry.card);
      } else {
        logHomepageWarn('score payload missing for pending card', {
          itemId: entry.itemId,
          trigger,
        });
        entry.card.removeAttribute(PROCESSING);
      }
    }
    if (scoredCards.length > 0) {
      applyLocalPersonalizationOrdering(scoredCards);
    }
  }
}

function cardContainsSponsoredMarker(card: HTMLElement): boolean {
  const text = card.textContent?.toLowerCase() ?? '';
  return (
    text.includes('sponsored') ||
    text.includes('sponsoreret') ||
    text.includes('promoted')
  );
}

function cardContainsExternalCallToAction(card: HTMLElement): boolean {
  const text = card.textContent?.toLowerCase() ?? '';
  return (
    text.includes('visit site') ||
    text.includes('besøg website') ||
    text.includes('learn more') ||
    text.includes('shop now')
  );
}

function isSponsoredCard(
  card: HTMLElement,
  linkKind: 'watch' | 'shorts' | 'other' | 'unknown',
): boolean {
  if (
    card.closest('ytd-ad-slot-renderer, ytd-display-ad-renderer, ytd-promoted-video-renderer')
  ) {
    return true;
  }

  if (cardContainsSponsoredMarker(card)) {
    return true;
  }

  return linkKind === 'other' && cardContainsExternalCallToAction(card);
}

const homepageScoreScheduler = createHomepageScoreScheduler(
  (trigger) => scoreCards(trigger),
  (trigger) => {
    logHomepageDebug('queued score pass while another pass was already running', {
      trigger,
    });
  },
);

function requestScoreCards(trigger: HomepageScoreTrigger): void {
  homepageScoreScheduler.request(trigger);
}

mountOverlay();
installRuntimeListeners();
installFeedRerankSettingListener();
installManualReviewSubmissionListener();
void (async () => {
  try {
    feedRerankEnabled = await loadFeedRerankEnabled();
  } catch {
    feedRerankEnabled = DEFAULT_FEED_RERANK_ENABLED;
  }

  try {
    channelTrustProfiles = await loadCachedChannelTrustProfiles();
  } catch {
    channelTrustProfiles = {};
  }

  void refreshChannelTrustProfiles();
  requestScoreCards('startup');
})();

const observer = new MutationObserver((mutations) => {
  if (isApplyingFeedRerank) {
    return;
  }
  if (!shouldRescoreFromMutations(mutations, OVERLAY_ID)) {
    return;
  }
  if (rescoreTimer !== null) {
    window.clearTimeout(rescoreTimer);
  }
  rescoreTimer = window.setTimeout(() => {
    rescoreTimer = null;
    requestScoreCards('mutation');
  }, 120);
});
observer.observe(document.body, { childList: true, subtree: true });
