import type { UserContext } from '@truthlens/shared-schemas';

const MUTED_CHANNELS_KEY = 'truthlens-muted-channels';

type ReadStorage = Pick<Storage, 'getItem'>;
type WriteStorage = Pick<Storage, 'setItem'>;
type ReadWriteStorage = ReadStorage & WriteStorage;

export function normalizeChannelName(value: string): string {
  return value.trim().toLowerCase();
}

function resolveBrowserStorage<TStorage>(storage: TStorage | undefined): TStorage | null {
  if (storage) {
    return storage;
  }

  try {
    return window.localStorage as TStorage;
  } catch {
    return null;
  }
}

function safeGetItem(storage: ReadStorage | null, key: string): string | null {
  if (!storage) {
    return null;
  }

  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function safeSetItem(storage: WriteStorage | null, key: string, value: string): void {
  if (!storage) {
    return;
  }

  try {
    storage.setItem(key, value);
  } catch {
    // Fail soft; muted-channel preferences should never break scoring.
  }
}

export function loadMutedChannels(storage?: ReadStorage): string[] {
  const raw = safeGetItem(resolveBrowserStorage(storage), MUTED_CHANNELS_KEY);
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
  storage?: WriteStorage,
): void {
  const normalized = Array.from(new Set(channels.map(normalizeChannelName).filter(Boolean)));
  safeSetItem(resolveBrowserStorage(storage), MUTED_CHANNELS_KEY, JSON.stringify(normalized));
}

export function muteChannel(
  channelName: string,
  storage?: ReadWriteStorage,
): string[] {
  const current = loadMutedChannels(storage);
  const next = Array.from(new Set([...current, normalizeChannelName(channelName)]));
  saveMutedChannels(next, storage);
  return next;
}

export function isChannelMuted(
  channelName: string,
  storage?: ReadStorage,
): boolean {
  return loadMutedChannels(storage).includes(normalizeChannelName(channelName));
}

export function buildUserContext(storage?: ReadStorage): UserContext {
  return {
    strict_mode: false,
    muted_channels: loadMutedChannels(storage),
    prior_corrections: 0,
  };
}
