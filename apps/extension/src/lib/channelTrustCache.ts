import type { FeedbackChannelProfile } from './api';

const CHANNEL_TRUST_CACHE_KEY = 'truthlens-feedback-channel-profiles';

export async function loadCachedChannelTrustProfiles(): Promise<
  Record<string, FeedbackChannelProfile>
> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return {};
  }

  const payload = await chrome.storage.local.get(CHANNEL_TRUST_CACHE_KEY);
  const profiles = payload?.[CHANNEL_TRUST_CACHE_KEY] as
    | Record<string, FeedbackChannelProfile>
    | undefined;
  return profiles ?? {};
}

export async function persistCachedChannelTrustProfiles(
  profiles: Record<string, FeedbackChannelProfile>,
): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return;
  }

  await chrome.storage.local.set({
    [CHANNEL_TRUST_CACHE_KEY]: profiles,
  });
}

export { CHANNEL_TRUST_CACHE_KEY };
