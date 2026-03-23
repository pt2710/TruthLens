import React from 'react';
import { createRoot } from 'react-dom/client';
import type { ScoreItemRequest, ScoreResult } from '@truthlens/shared-schemas';

import { batchScoreFeedItems, sendFeedbackEvent } from './lib/api';
import { buildUserContext, isChannelMuted, muteChannel } from './lib/userPreferences';
import { App } from './overlay/App';
import { useOverlayStore } from './overlay/store';
import './styles.css';

const OVERLAY_ID = 'truthlens-overlay-root';
const PROCESSED = 'data-truthlens-processed';
const PROCESSING = 'data-truthlens-processing';
let rescoreTimer: number | null = null;
const BATCH_SIZE = 12;

type PendingCard = {
  card: HTMLElement;
  itemId: string;
  channelName: string;
  request: ScoreItemRequest;
};

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
    card.querySelector<HTMLAnchorElement>('a#thumbnail, a[href*="watch"], a[href*="/shorts/"]')?.href || '';
  if (href) {
    return href;
  }
  return `card-${index + 1}`;
}

function createFeedbackPayload(
  itemId: string,
  channelName: string,
  actionShown: 'none' | 'badge' | 'blur' | 'hide' | 'ask-report',
  userAction: string,
  beforeScore: number,
) {
  return {
    item_id: itemId,
    item_hash: null,
    channel_name: channelName,
    model_version: 'extension-runtime',
    policy_version: 'adaptive-threshold-v1',
    action_shown: actionShown,
    user_action: userAction,
    explanation_id: null,
    before_score: beforeScore,
    after_score: beforeScore,
    timestamp: new Date().toISOString(),
  } as const;
}

function attachActions(
  card: HTMLElement,
  itemId: string,
  channelName: string,
  score: ScoreResult,
) {
  if (card.querySelector('.truthlens-action-row')) {
    return;
  }

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
  details.textContent =
    score.reasons.length > 0
      ? score.reasons.join(' ')
      : 'No explanation available for this item.';

  whyButton.addEventListener('click', () => {
    details.hidden = !details.hidden;
  });

  safeButton.addEventListener('click', () => {
    void sendFeedbackEvent(
      createFeedbackPayload(itemId, channelName, score.recommended_action, 'not-misleading', score.risk_score),
    );
    card.classList.remove('truthlens-card-hidden');
    card.classList.remove('truthlens-card-blur');
  });

  hideButton.addEventListener('click', () => {
    card.classList.add('truthlens-card-hidden');
    void sendFeedbackEvent(
      createFeedbackPayload(itemId, channelName, score.recommended_action, 'hide-locally', score.risk_score),
    );
  });

  muteButton.addEventListener('click', () => {
    muteChannel(channelName);
    card.classList.add('truthlens-card-hidden');
    void sendFeedbackEvent(
      createFeedbackPayload(itemId, channelName, score.recommended_action, 'mute-channel-local', score.risk_score),
    );
  });

  reportButton.addEventListener('click', () => {
    void sendFeedbackEvent(
      createFeedbackPayload(itemId, channelName, score.recommended_action, 'report', score.risk_score),
    );
  });

  actionRow.append(whyButton, safeButton, hideButton, muteButton, reportButton);
  card.append(actionRow, details);
}

function buildPendingCard(card: HTMLElement, index: number): PendingCard | null {
  if (card.getAttribute(PROCESSED) === 'true' || card.getAttribute(PROCESSING) === 'true') {
    return null;
  }

  const title = extractText(card, '#video-title, h3, a[title]') || `Untitled item ${index + 1}`;
  const channelName =
    extractText(card, 'ytd-channel-name, #channel-name, [id="channel-info"] a') || 'Unknown channel';
  if (isChannelMuted(channelName)) {
    card.classList.add('truthlens-card-hidden');
    card.setAttribute(PROCESSED, 'true');
    return null;
  }
  const thumbnailRef =
    card.querySelector<HTMLImageElement>('img')?.getAttribute('src') || null;
  const itemId = buildItemId(card, index);
  card.setAttribute(PROCESSING, 'true');
  return {
    card,
    itemId,
    channelName,
    request: {
      item_id: itemId,
      title,
      thumbnail_ref: thumbnailRef,
      transcript_excerpt: extractText(card, '#description-text, #metadata-line, .metadata-snippet'),
      metadata: {},
      channel: {
        channel_name: channelName,
        prior_flags: 0,
        channel_history_features: {},
      },
      user_context: buildUserContext(),
    },
  };
}

function applyScoreToCard(pendingCard: PendingCard, score: ScoreResult) {
  const { card, itemId, channelName } = pendingCard;
  useOverlayStore.getState().recordScore(itemId, score);

  if (score.recommended_action !== 'none' && !card.querySelector('.truthlens-card-flag')) {
    const flag = document.createElement('span');
    flag.className = 'truthlens-card-flag';
    flag.textContent = `TruthLens: ${score.recommended_action}`;
    card.appendChild(flag);
  }

  if (score.recommended_action === 'blur') {
    card.classList.add('truthlens-card-blur');
  }
  if (score.recommended_action === 'hide') {
    card.classList.add('truthlens-card-hidden');
  }

  attachActions(card, itemId, channelName, score);
  card.setAttribute(PROCESSED, 'true');
  card.removeAttribute(PROCESSING);
}

function chunk<T>(items: T[], size: number): T[][] {
  const batches: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    batches.push(items.slice(index, index + size));
  }
  return batches;
}

async function scoreCards() {
  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const cards = Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')));
  const pendingCards = cards
    .map((card, index) => buildPendingCard(card, index))
    .filter((entry): entry is PendingCard => entry !== null);

  for (const batch of chunk(pendingCards, BATCH_SIZE)) {
    const scores = await batchScoreFeedItems(batch.map((entry) => entry.request));
    for (const entry of batch) {
      const score = scores[entry.itemId];
      if (score) {
        applyScoreToCard(entry, score);
      } else {
        entry.card.removeAttribute(PROCESSING);
      }
    }
  }
}

mountOverlay();
void scoreCards();

const observer = new MutationObserver(() => {
  if (rescoreTimer !== null) {
    window.clearTimeout(rescoreTimer);
  }
  rescoreTimer = window.setTimeout(() => {
    void scoreCards();
  }, 120);
});
observer.observe(document.body, { childList: true, subtree: true });
