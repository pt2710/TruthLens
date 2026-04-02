import { describe, expect, it, vi } from 'vitest';

import { fetchYouTubeWatchMetadata, parsePlayerResponseFromHtml } from './youtubeWatchMetadata';

describe('youtube watch metadata', () => {
  it('parses player response JSON from watch HTML', () => {
    const html = `
      <html><body><script>
        var ytInitialPlayerResponse = {"videoDetails":{"shortDescription":"Line one\\nLine two"}};
      </script></body></html>
    `;

    const parsed = parsePlayerResponseFromHtml(html);

    expect(parsed?.videoDetails?.shortDescription).toBe('Line one\nLine two');
  });

  it('extracts watch metadata, transcript availability, and recent channel titles', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/watch?v=test-item')) {
        return {
          ok: true,
          text: async () =>
            '<html><body><script>var ytInitialPlayerResponse = {"videoDetails":{"shortDescription":"This video explains the actual build process without exaggerated claims."},"captions":{"playerCaptionsTracklistRenderer":{"captionTracks":[{"baseUrl":"https://www.youtube.com/api/timedtext?v=test-item&lang=en","languageCode":"en"}]}}};</script><script>var ytInitialData = {"ownerProfileUrl":"/@contextfirstmedia"};</script></body></html>',
        };
      }

      if (url.includes('/@contextfirstmedia/videos')) {
        return {
          ok: true,
          text: async () =>
            '<html><body><a id="video-title">Garage Build Walkthrough</a><a id="video-title">How We Actually Tuned the Sleeper</a><a id="video-title">No Clickbait Dyno Results</a></body></html>',
        };
      }

      return {
        ok: true,
        json: async () => ({
          events: [
            { segs: [{ utf8: 'The video shows a garage build walkthrough. ' }] },
            { segs: [{ utf8: 'The spoken explanation matches the visual framing.' }] },
          ],
        }),
      };
    });

    const metadata = await fetchYouTubeWatchMetadata(
      'https://www.youtube.com/watch?v=test-item',
      fetchMock as unknown as typeof fetch,
    );

    expect(metadata.descriptionSnapshot).toContain('actual build process');
    expect(metadata.transcriptExcerpt).toContain('garage build walkthrough');
    expect(metadata.transcriptAvailable).toBe(true);
    expect(metadata.channelUrl).toBe('https://www.youtube.com/@contextfirstmedia');
    expect(metadata.channelContext).toContain('Garage Build Walkthrough');
    expect(metadata.channelContext).toContain('No Clickbait Dyno Results');
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
