const UNTITLED_ITEM_PATTERN = /^Untitled item \d+$/i;
const UNKNOWN_CHANNEL_NAME = 'unknown channel';

export type FeedCardStabilitySnapshot = {
  itemId: string;
  title: string;
  channelName: string;
  linkUrl: string | null;
};

function normalizeWhitespace(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

export function buildStableFeedCardSignature(snapshot: FeedCardStabilitySnapshot): string {
  return [
    normalizeWhitespace(snapshot.itemId),
    normalizeWhitespace(snapshot.title),
    normalizeWhitespace(snapshot.channelName).toLowerCase(),
  ].join('||');
}

export function isReadyForStableFeedScoring(
  snapshot: FeedCardStabilitySnapshot,
): boolean {
  const title = normalizeWhitespace(snapshot.title);
  const channelName = normalizeWhitespace(snapshot.channelName).toLowerCase();

  return (
    snapshot.linkUrl !== null &&
    snapshot.linkUrl.trim().length > 0 &&
    title.length > 0 &&
    !UNTITLED_ITEM_PATTERN.test(title) &&
    channelName.length > 0 &&
    channelName !== UNKNOWN_CHANNEL_NAME
  );
}
