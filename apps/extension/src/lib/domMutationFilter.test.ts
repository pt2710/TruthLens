// @vitest-environment jsdom

import { afterEach, describe, expect, it } from 'vitest';

import { shouldRescoreFromMutations } from './domMutationFilter';

const OVERLAY_ID = 'truthlens-overlay-root';

async function collectMutations(run: () => void): Promise<MutationRecord[]> {
  const mutations: MutationRecord[] = [];
  const observer = new MutationObserver((records) => {
    mutations.push(...records);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  run();

  await new Promise((resolve) => window.setTimeout(resolve, 0));
  observer.disconnect();
  return mutations;
}

describe('shouldRescoreFromMutations', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('ignores TruthLens-owned card augmentations', async () => {
    document.body.innerHTML = '<ytd-rich-item-renderer id="card"></ytd-rich-item-renderer>';
    const card = document.getElementById('card');
    if (!card) {
      throw new Error('Expected a card element in the test DOM.');
    }

    const mutations = await collectMutations(() => {
      const flag = document.createElement('span');
      flag.className = 'truthlens-card-flag';
      card.appendChild(flag);
    });

    expect(shouldRescoreFromMutations(mutations, OVERLAY_ID)).toBe(false);
  });

  it('rescans when a new YouTube card is added to the page', async () => {
    const mutations = await collectMutations(() => {
      const card = document.createElement('ytd-rich-item-renderer');
      document.body.appendChild(card);
    });

    expect(shouldRescoreFromMutations(mutations, OVERLAY_ID)).toBe(true);
  });

  it('rescans when an existing card gets non-TruthLens content updates', async () => {
    document.body.innerHTML =
      '<ytd-rich-item-renderer><a id="video-title">Original title</a></ytd-rich-item-renderer>';
    const title = document.getElementById('video-title');
    if (!title) {
      throw new Error('Expected a title element in the test DOM.');
    }

    const mutations = await collectMutations(() => {
      title.textContent = 'Updated title';
    });

    expect(shouldRescoreFromMutations(mutations, OVERLAY_ID)).toBe(true);
  });
});
