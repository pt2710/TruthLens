import React from 'react';
import { createRoot } from 'react-dom/client';

import { createBootstrapScore } from './lib/mockScore';
import { App } from './overlay/App';
import { useOverlayStore } from './overlay/store';
import './styles.css';

const OVERLAY_ID = 'truthlens-overlay-root';
const PROCESSED = 'data-truthlens-processed';

function mountOverlay() {
  if (document.getElementById(OVERLAY_ID)) {
    return;
  }

  const rootNode = document.createElement('div');
  rootNode.id = OVERLAY_ID;
  document.body.appendChild(rootNode);
  createRoot(rootNode).render(<App />);
}

function scoreCards() {
  const selectors = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
  const cards = document.querySelectorAll<HTMLElement>(selectors.join(','));

  cards.forEach((card, index) => {
    if (card.getAttribute(PROCESSED) === 'true') {
      return;
    }

    const titleNode = card.querySelector('#video-title, h3, a[title]');
    const title = titleNode?.textContent?.trim() || `Untitled item ${index + 1}`;
    const score = createBootstrapScore({
      item_id: `card-${index + 1}`,
      title,
      thumbnail_ref: null,
      metadata: {},
      channel: {
        channel_name: 'Unknown channel',
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

    card.setAttribute(PROCESSED, 'true');
  });
}

mountOverlay();
scoreCards();

const observer = new MutationObserver(() => scoreCards());
observer.observe(document.body, { childList: true, subtree: true });
