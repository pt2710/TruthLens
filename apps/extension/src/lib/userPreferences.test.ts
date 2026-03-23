// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import { buildUserContext, isChannelMuted, muteChannel, normalizeChannelName } from './userPreferences';

function createMemoryStorage() {
  const data = new Map<string, string>();

  return {
    getItem(key: string) {
      return data.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      data.set(key, value);
    },
    clear() {
      data.clear();
    },
  };
}

describe('userPreferences', () => {
  const storage = createMemoryStorage();

  beforeEach(() => {
    storage.clear();
  });

  it('normalizes channel names consistently', () => {
    expect(normalizeChannelName('  My Channel  ')).toBe('my channel');
  });

  it('persists muted channels and exposes them in user context', () => {
    muteChannel('My Channel', storage);

    expect(isChannelMuted('my channel', storage)).toBe(true);
    expect(buildUserContext(storage).muted_channels).toContain('my channel');
  });
});
