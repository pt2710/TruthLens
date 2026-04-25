import { describe, expect, it } from 'vitest';

import {
  buildStableFeedCardSignature,
  isReadyForStableFeedScoring,
} from './feedCardStability';

describe('feedCardStability', () => {
  it('waits until a homepage card has stable title, channel, and link identity', () => {
    expect(
      isReadyForStableFeedScoring({
        itemId: 'card-1',
        title: 'Untitled item 1',
        channelName: 'Unknown channel',
        linkUrl: null,
      }),
    ).toBe(false);

    expect(
      isReadyForStableFeedScoring({
        itemId: 'https://www.youtube.com/watch?v=abc123',
        title: 'Weekly launch schedule and mission recap',
        channelName: 'Context First Media',
        linkUrl: 'https://www.youtube.com/watch?v=abc123',
      }),
    ).toBe(true);
  });

  it('builds a stable signature from feed identity instead of transient metadata snippets', () => {
    expect(
      buildStableFeedCardSignature({
        itemId: 'https://www.youtube.com/watch?v=abc123',
        title: 'Breaking aliens confirmed over Europe',
        channelName: 'OpenSky Alerts',
        linkUrl: 'https://www.youtube.com/watch?v=abc123',
      }),
    ).toBe(
      buildStableFeedCardSignature({
        itemId: 'https://www.youtube.com/watch?v=abc123',
        title: 'Breaking aliens confirmed over Europe',
        channelName: 'OpenSky Alerts',
        linkUrl: 'https://www.youtube.com/watch?v=abc123',
      }),
    );
  });
});
