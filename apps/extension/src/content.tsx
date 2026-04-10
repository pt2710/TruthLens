import React from 'react';
import { createRoot } from 'react-dom/client';
import type {
  BrowserObservationRecord,
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
  buildPersonalizationSnapshot,
  shouldShowPersonalizationBadge,
  type PersonalizationSnapshot,
} from './lib/personalization';
import { inferReviewPromptDecision } from './lib/reviewPrompts';
import { shouldRescoreFromMutations } from './lib/domMutationFilter';
import { buildUserContext, isChannelMuted, muteChannel } from './lib/userPreferences';
import { App } from './overlay/App';
import { type ManualReportTarget, useOverlayStore } from './overlay/store';
import './styles.css';

const OVERLAY_ID = 'truthlens-overlay-root';
const PROCESSED = 'data-truthlens-processed';
const PROCESSING = 'data-truthlens-processing';
const ITEM_ID = 'data-truthlens-item-id';
const SIGNATURE = 'data-truthlens-signature';
const PERSONALIZATION = 'data-truthlens-personalization';
const PERSONALIZATION_SCORE = 'data-truthlens-personalization-score';
const ORIGINAL_INDEX = 'data-truthlens-original-index';
const OBSERVATION_ID = 'data-truthlens-observation-id';
const UNKNOWN_CHANNEL_NAME = 'Unknown channel';
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
let channelTrustProfiles: Record<string, FeedbackChannelProfile> = {};
let autoOpenedReviewPrompt = false;
const OBSERVATION_SESSION_ID = createClientId('obs-session');

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
  request: ScoreItemRequest;
};

type ManualReportMessage = {
  type: 'TRUTHLENS_OPEN_MANUAL_REPORT';
  linkUrl?: string | null;
  srcUrl?: string | null;
  pageUrl?: string | null;
  workflowMode?: ManualReportWorkflowMode;
};

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

function buildItemId(card: HTMLElement, index: number): string {
  const href =
    card.querySelector<HTMLAnchorElement>(
      'a#thumbnail, a[href*="watch"], a[href*="/shorts/"], a[href*="playlist?list="]',
    )?.href || '';
  if (href) {
    return href;
  }
  return `card-${index + 1}`;
}

function buildCardSignature(
  title: string,
  channelName: string,
  thumbnailRef: string | null,
  transcriptExcerpt: string | null,
) {
  return [title, channelName, thumbnailRef || '', transcriptExcerpt || ''].join('||');
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

function extractChannelIdentity(card: HTMLElement): { channelName: string; channelUrl: string | null } {
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
  return {
    channelName: anchorText || selectorText || derivedName || UNKNOWN_CHANNEL_NAME,
    channelUrl,
  };
}

async function refreshChannelTrustProfiles(): Promise<void> {
  try {
    const summary = await fetchFeedbackSummary();
    channelTrustProfiles = summary.channel_profiles ?? {};
  } catch {
    // Fail soft and keep the previous trust snapshot.
  }
}

function getScoreTone(score: number): 'high' | 'medium' | 'low' {
  if (score >= 7.5) {
    return 'high';
  }
  if (score >= 4.5) {
    return 'medium';
  }
  return 'low';
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
  const title = extractText(card, '#video-title, h3, a[title]') || `Untitled item ${index + 1}`;
  const { channelName, channelUrl } = extractChannelIdentity(card);
  const thumbnailRef = card.querySelector<HTMLImageElement>('img')?.getAttribute('src') || null;
  const descriptionSnapshot = extractText(card, '#description-text, #metadata-line, .metadata-snippet');
  const transcriptExcerpt = descriptionSnapshot;
  const linkUrl =
    card.querySelector<HTMLAnchorElement>(
      'a#thumbnail, a[href*="watch"], a[href*="/shorts/"], a[href*="playlist?list="]',
    )
      ?.href || null;
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
  const signature = buildCardSignature(title, channelName, thumbnailRef, transcriptExcerpt);
  const taxonomyHints = estimateTaxonomyHints(title, channelName, descriptionSnapshot);
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
    request: {
      item_id: itemId,
      title,
      thumbnail_ref: thumbnailRef,
      transcript_excerpt: transcriptExcerpt,
      channel: {
        channel_name: channelName,
        channel_url: channelUrl,
        prior_flags: 0,
        channel_history_features: taxonomyHints,
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
    score,
  };
}

function openManualReport(entry: PendingCard, score: ScoreResult | null) {
  useOverlayStore.getState().openManualReport(buildManualReportTarget(entry, score, 'report'));
}

function openManualReview(entry: PendingCard, score: ScoreResult | null, workflowMode: ManualReportWorkflowMode) {
  useOverlayStore.getState().openManualReport(buildManualReportTarget(entry, score, workflowMode));
}

function clearCardAugmentations(card: HTMLElement) {
  card.classList.remove('truthlens-card-hidden');
  card.classList.remove('truthlens-card-blur');
  card.classList.remove('truthlens-card-boosted');
  card.classList.remove('truthlens-card-steady');
  card.classList.remove('truthlens-card-downranked');
  card.querySelector('.truthlens-card-flag')?.remove();
  card.querySelector('.truthlens-review-prompt')?.remove();
  card.querySelector('.truthlens-action-row')?.remove();
  card.querySelector('.truthlens-details')?.remove();
}

function syncPersonalizationPresentation(
  card: HTMLElement,
  score: ScoreResult,
  channelName: string,
): PersonalizationSnapshot {
  const profile = isUnknownChannelName(channelName)
    ? undefined
    : channelTrustProfiles[normalizeChannelKey(channelName)];
  const personalization = buildPersonalizationSnapshot(score, profile);
  const trustTone = getScoreTone(personalization.rankingScore);
  const shouldShowFlag = shouldShowPersonalizationBadge(personalization, score);

  card.classList.remove('truthlens-card-boosted');
  card.classList.remove('truthlens-card-steady');
  card.classList.remove('truthlens-card-downranked');
  card.classList.add(`truthlens-card-${personalization.bucket}`);
  card.setAttribute(PERSONALIZATION, personalization.bucket);
  card.setAttribute(PERSONALIZATION_SCORE, personalization.displayScore.toFixed(2));
  card.setAttribute(
    'data-truthlens-personalization-reasons',
    `TruthLens score ${personalization.displayScore.toFixed(1)}/10 with local personalization ${personalization.rankingScore.toFixed(1)}/10: ${personalization.reasons.join('; ')}`,
  );

  const existingFlag = card.querySelector<HTMLElement>('.truthlens-card-flag');
  if (!shouldShowFlag) {
    existingFlag?.remove();
    return personalization;
  }

  const flag = existingFlag ?? document.createElement('span');
  flag.className = `truthlens-card-flag truthlens-card-flag-${trustTone} truthlens-card-flag-${personalization.bucket}`;
  flag.textContent = personalization.displayScore.toFixed(1);
  flag.title = `TruthLens score ${personalization.displayScore.toFixed(1)}/10. Local personalization ${personalization.rankingScore.toFixed(1)}/10. Channel trust ${personalization.trustScore.toFixed(1)}/10. ${personalization.reasons.join('; ')}.`;
  if (!existingFlag) {
    card.appendChild(flag);
  }

  return personalization;
}

function applyLocalPersonalizationOrdering() {
  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const scoresByItemId = useOverlayStore.getState().scoresByItemId;

  Array.from(document.querySelectorAll<HTMLElement>(selectors.join(','))).forEach((card, index) => {
    const itemId = card.getAttribute(ITEM_ID);
    if (!itemId) {
      ensureOriginalIndex(card, index);
      if (card.style.order) {
        card.style.order = '';
      }
      return;
    }

    const score = scoresByItemId[itemId];
    if (!score) {
      ensureOriginalIndex(card, index);
      if (card.style.order) {
        card.style.order = '';
      }
      return;
    }

    const { channelName } = extractChannelIdentity(card);
    ensureOriginalIndex(card, index);
    syncPersonalizationPresentation(card, score, channelName);
    if (card.style.order) {
      card.style.order = '';
    }
  });
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
    after_score: beforeScore,
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
    card.classList.add('truthlens-card-hidden');
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
    card.classList.add('truthlens-card-hidden');
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
  if (card.getAttribute(PROCESSING) === 'true') {
    return null;
  }

  const entry = extractCardContext(card, index);
  if (!entry) {
    return null;
  }
  const { title, channelName, thumbnailRef, transcriptExcerpt, itemId, signature } = entry;
  if (!isUnknownChannelName(channelName) && isChannelMuted(channelName)) {
    card.classList.add('truthlens-card-hidden');
    card.setAttribute(PROCESSED, 'true');
    card.setAttribute(
      SIGNATURE,
      buildCardSignature(title, channelName, thumbnailRef, transcriptExcerpt),
    );
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

  syncPersonalizationPresentation(card, score, pendingCard.channelName);

  if (score.recommended_action === 'hide') {
    card.classList.add('truthlens-card-hidden');
  }
  if (score.recommended_action === 'blur') {
    card.classList.add('truthlens-card-blur');
  }
  const musicLikelihood = Number(
    pendingCard.request.channel.channel_history_features.music_likelihood ?? 0,
  );
  const reviewPrompt = inferReviewPromptDecision(score, musicLikelihood);
  if (reviewPrompt !== null) {
    card.setAttribute('data-truthlens-review-mode', reviewPrompt.workflowMode);
    if (score.recommended_action !== 'hide') {
      const reviewButton = document.createElement('button');
      reviewButton.type = 'button';
      reviewButton.className = `truthlens-review-prompt truthlens-review-prompt-${reviewPrompt.workflowMode}`;
      reviewButton.textContent = reviewPrompt.label;
      reviewButton.title = reviewPrompt.reason;
      reviewButton.addEventListener('click', () => {
        openManualReview(pendingCard, score, reviewPrompt.workflowMode);
      });
      card.appendChild(reviewButton);
    }
    if (!autoOpenedReviewPrompt && reviewPrompt.autoOpen && useOverlayStore.getState().manualReportTarget === null) {
      autoOpenedReviewPrompt = true;
      window.setTimeout(() => {
        if (useOverlayStore.getState().manualReportTarget === null) {
          openManualReview(pendingCard, score, reviewPrompt.workflowMode);
        }
      }, 240);
    }
  } else {
    card.removeAttribute('data-truthlens-review-mode');
  }
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

function installRuntimeListeners() {
  if (typeof chrome === 'undefined' || !chrome.runtime?.onMessage) {
    return;
  }

  chrome.runtime.onMessage.addListener((message: ManualReportMessage, _sender, sendResponse) => {
    if (message?.type !== 'TRUTHLENS_OPEN_MANUAL_REPORT') {
      return;
    }

    const target = findManualReportTarget(message);
    if (!target) {
      sendResponse({ ok: false });
      return;
    }

    useOverlayStore.getState().openManualReport(target);
    sendResponse({ ok: true });
  });
}

async function scoreCards() {
  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const cards = Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')));
  const pendingCards = cards
    .map((card, index) => buildPendingCard(card, index))
    .filter((entry): entry is PendingCard => entry !== null);

  const resolvedScores: Record<string, ScoreResult> = {};
  for (const batch of chunk(pendingCards, BATCH_SIZE)) {
    const scores = await batchScoreFeedItems(batch.map((entry) => entry.request));
    for (const entry of batch) {
      const score = scores[entry.itemId];
      if (score) {
        resolvedScores[entry.itemId] = score;
      } else {
        entry.card.removeAttribute(PROCESSING);
      }
    }
  }
  await refreshChannelTrustProfiles();
  for (const entry of pendingCards) {
    const score = resolvedScores[entry.itemId];
    if (score) {
      applyScoreToCard(entry, score);
    }
  }
  applyLocalPersonalizationOrdering();
}

mountOverlay();
installRuntimeListeners();
void scoreCards();

const observer = new MutationObserver((mutations) => {
  if (!shouldRescoreFromMutations(mutations, OVERLAY_ID)) {
    return;
  }
  if (rescoreTimer !== null) {
    window.clearTimeout(rescoreTimer);
  }
  rescoreTimer = window.setTimeout(() => {
    rescoreTimer = null;
    void scoreCards();
  }, 120);
});
observer.observe(document.body, { childList: true, subtree: true });
