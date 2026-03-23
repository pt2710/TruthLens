import type { UserContext } from '@truthlens/shared-schemas';

const MUTED_CHANNELS_KEY = 'truthlens-muted-channels';

export function normalizeChannelName(value: string): string {
  return value.trim().toLowerCase();
}

export function loadMutedChannels(storage: Pick<Storage, 'getItem'> = window.localStorage): string[] {
  const raw = storage.getItem(MUTED_CHANNELS_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as string[];
    return parsed.map(normalizeChannelName).filter(Boolean);
  } catch {
    return [];
  }
}

export function saveMutedChannels(
  channels: string[],
  storage: Pick<Storage, 'setItem'> = window.localStorage,
): void {
  const normalized = Array.from(new Set(channels.map(normalizeChannelName).filter(Boolean)));
  storage.setItem(MUTED_CHANNELS_KEY, JSON.stringify(normalized));
}

export function muteChannel(
  channelName: string,
  storage: Pick<Storage, 'getItem' | 'setItem'> = window.localStorage,
): string[] {
  const current = loadMutedChannels(storage);
  const next = Array.from(new Set([...current, normalizeChannelName(channelName)]));
  saveMutedChannels(next, storage);
  return next;
}

export function isChannelMuted(
  channelName: string,
  storage: Pick<Storage, 'getItem'> = window.localStorage,
): boolean {
  return loadMutedChannels(storage).includes(normalizeChannelName(channelName));
}

export function buildUserContext(
  storage: Pick<Storage, 'getItem'> = window.localStorage,
): UserContext {
  return {
    strict_mode: false,
    muted_channels: loadMutedChannels(storage),
    prior_corrections: 0,
  };
}
