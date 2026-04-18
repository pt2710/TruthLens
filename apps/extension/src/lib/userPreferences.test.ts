// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildUserContext,
  isChannelMuted,
  loadMutedChannels,
  muteChannel,
  normalizeChannelName,
  saveMutedChannels,
} from './userPreferences';

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
    vi.restoreAllMocks();
  });

  it('normalizes channel names consistently', () => {
    expect(normalizeChannelName('  My Channel  ')).toBe('my channel');
  });

  it('persists muted channels and exposes them in user context', () => {
    muteChannel('My Channel', storage);

    expect(isChannelMuted('my channel', storage)).toBe(true);
    expect(buildUserContext(storage).muted_channels).toContain('my channel');
  });

  it('fails soft when custom storage access throws', () => {
    const throwingStorage = {
      getItem() {
        throw new Error('blocked');
      },
      setItem() {
        throw new Error('blocked');
      },
    };

    expect(loadMutedChannels(throwingStorage)).toEqual([]);
    expect(() => saveMutedChannels(['My Channel'], throwingStorage)).not.toThrow();
    expect(muteChannel('My Channel', throwingStorage)).toEqual(['my channel']);
    expect(isChannelMuted('My Channel', throwingStorage)).toBe(false);
    expect(buildUserContext(throwingStorage).muted_channels).toEqual([]);
  });

  it('fails soft when window.localStorage is unavailable', () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new Error('localStorage unavailable');
    });

    expect(loadMutedChannels()).toEqual([]);
    expect(() => saveMutedChannels(['My Channel'])).not.toThrow();
    expect(muteChannel('My Channel')).toEqual(['my channel']);
    expect(isChannelMuted('My Channel')).toBe(false);
    expect(buildUserContext().muted_channels).toEqual([]);
  });
});
