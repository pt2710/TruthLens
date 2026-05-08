// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import {
  RERANK_CHUNK_ID_ATTR,
  RERANK_CHUNK_SEALED_ATTR,
  shouldRestoreOriginalOrderingWhenDisabled,
} from './feedRerankGate';

describe('feedRerankGate', () => {
  it('does not restore ordering when no rerank markers exist', () => {
    const card = document.createElement('div');
    expect(shouldRestoreOriginalOrderingWhenDisabled([card])).toBe(false);
  });

  it('restores ordering when a rerank chunk marker exists', () => {
    const card = document.createElement('div');
    card.setAttribute(RERANK_CHUNK_ID_ATTR, 'chunk-1');
    expect(shouldRestoreOriginalOrderingWhenDisabled([card])).toBe(true);
  });

  it('restores ordering when a rerank chunk is sealed', () => {
    const card = document.createElement('div');
    card.setAttribute(RERANK_CHUNK_SEALED_ATTR, 'true');
    expect(shouldRestoreOriginalOrderingWhenDisabled([card])).toBe(true);
  });
});

