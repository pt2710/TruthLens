import React from 'react';
import { createRoot } from 'react-dom/client';

import { sendFeedbackEvent, scoreFeedItem } from './lib/api';
import { App } from './overlay/App';
import { useOverlayStore } from './overlay/store';
import './styles.css';

const OVERLAY_ID = 'truthlens-overlay-root';
const PROCESSED = 'data-truthlens-processed';
const PROCESSING = 'data-truthlens-processing';

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
  actionShown: 'none' | 'badge' | 'blur' | 'hide' | 'ask-report',
  userAction: string,
  beforeScore: number,
) {
  return {
    item_id: itemId,
    item_hash: null,
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
  score: Awaited<ReturnType<typeof scoreFeedItem>>,
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
      createFeedbackPayload(itemId, score.recommended_action, 'not-misleading', score.risk_score),
    );
    card.classList.remove('truthlens-card-blur');
  });

  hideButton.addEventListener('click', () => {
    card.classList.add('truthlens-card-hidden');
    void sendFeedbackEvent(
      createFeedbackPayload(itemId, score.recommended_action, 'hide-locally', score.risk_score),
    );
  });

  reportButton.addEventListener('click', () => {
    void sendFeedbackEvent(
      createFeedbackPayload(itemId, score.recommended_action, 'report', score.risk_score),
    );
  });

  actionRow.append(whyButton, safeButton, hideButton, reportButton);
  card.append(actionRow, details);
}

async function processCard(card: HTMLElement, index: number) {
  if (card.getAttribute(PROCESSED) === 'true' || card.getAttribute(PROCESSING) === 'true') {
    return;
  }

  card.setAttribute(PROCESSING, 'true');
  try {
    const title = extractText(card, '#video-title, h3, a[title]') || `Untitled item ${index + 1}`;
    const channelName =
      extractText(card, 'ytd-channel-name, #channel-name, [id="channel-info"] a') || 'Unknown channel';
    const thumbnailRef =
      card.querySelector<HTMLImageElement>('img')?.getAttribute('src') || null;
    const itemId = buildItemId(card, index);

    const score = await scoreFeedItem({
      item_id: itemId,
      title,
      thumbnail_ref: thumbnailRef,
      metadata: {},
      channel: {
        channel_name: channelName,
        prior_flags: 0,
      },
    });

    useOverlayStore.getState().recordScore(score);

    if (score.recommended_action !== 'none') {
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

    attachActions(card, itemId, score);
    card.setAttribute(PROCESSED, 'true');
  } finally {
    card.removeAttribute(PROCESSING);
  }
}

async function scoreCards() {
  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const cards = Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')));
  await Promise.all(cards.map((card, index) => processCard(card, index)));
}

mountOverlay();
void scoreCards();

const observer = new MutationObserver(() => {
  void scoreCards();
});
observer.observe(document.body, { childList: true, subtree: true });
