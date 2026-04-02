export type YouTubeWatchMetadata = {
  descriptionSnapshot: string | null;
  transcriptExcerpt: string | null;
  transcriptAvailable: boolean | null;
  channelUrl: string | null;
  channelContext: string | null;
};

type CaptionTrack = {
  baseUrl?: string;
  languageCode?: string;
  kind?: string;
};

type PlayerResponse = {
  videoDetails?: {
    shortDescription?: string;
  };
  captions?: {
    playerCaptionsTracklistRenderer?: {
      captionTracks?: CaptionTrack[];
    };
  };
};

function collapseWhitespace(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/\s+/g, ' ').trim();
  return normalized.length > 0 ? normalized : null;
}

function excerpt(value: string | null, maxLength = 360): string | null {
  if (!value) {
    return null;
  }
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1).trimEnd()}…`;
}

function decodeEscapedYoutubeString(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return value
    .replace(/\\u0026/g, '&')
    .replace(/\\u003d/g, '=')
    .replace(/\\u002f/g, '/')
    .replace(/\\\//g, '/')
    .replace(/\\n/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeAbsoluteUrl(value: string | null, baseUrl: string): string | null {
  if (!value) {
    return null;
  }
  try {
    return new URL(value, baseUrl).toString();
  } catch {
    return value;
  }
}

function stripHtmlTags(value: string): string {
  return value.replace(/<[^>]+>/g, ' ');
}

function parseHtmlDocument(html: string): Document | null {
  if (typeof DOMParser === 'undefined') {
    return null;
  }
  try {
    return new DOMParser().parseFromString(html, 'text/html');
  } catch {
    return null;
  }
}

function extractJsonObject(source: string, marker: string): string | null {
  const markerIndex = source.indexOf(marker);
  if (markerIndex < 0) {
    return null;
  }
  const startIndex = source.indexOf('{', markerIndex + marker.length);
  if (startIndex < 0) {
    return null;
  }

  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = startIndex; index < source.length; index += 1) {
    const character = source[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (character === '\\') {
        escaped = true;
      } else if (character === '"') {
        inString = false;
      }
      continue;
    }

    if (character === '"') {
      inString = true;
      continue;
    }
    if (character === '{') {
      depth += 1;
      continue;
    }
    if (character === '}') {
      depth -= 1;
      if (depth === 0) {
        return source.slice(startIndex, index + 1);
      }
    }
  }

  return null;
}

export function parsePlayerResponseFromHtml(html: string): PlayerResponse | null {
  const jsonText =
    extractJsonObject(html, 'var ytInitialPlayerResponse = ') ??
    extractJsonObject(html, 'ytInitialPlayerResponse = ');
  if (!jsonText) {
    return null;
  }
  try {
    return JSON.parse(jsonText) as PlayerResponse;
  } catch {
    return null;
  }
}

function chooseCaptionTrack(playerResponse: PlayerResponse | null): CaptionTrack | null {
  const tracks =
    playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks ?? [];
  if (tracks.length === 0) {
    return null;
  }
  return (
    tracks.find((track) => track.languageCode?.toLowerCase().startsWith('en') && track.kind !== 'asr') ??
    tracks.find((track) => track.kind !== 'asr') ??
    tracks[0]
  );
}

function transcriptSnippetFromJson3(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object' || !('events' in payload)) {
    return null;
  }
  const events = Array.isArray((payload as { events?: unknown[] }).events)
    ? (payload as { events: Array<{ segs?: Array<{ utf8?: string }> }> }).events
    : [];
  const parts: string[] = [];
  for (const event of events) {
    for (const segment of event.segs ?? []) {
      if (typeof segment.utf8 === 'string') {
        parts.push(segment.utf8);
      }
    }
    if (parts.join(' ').length >= 360) {
      break;
    }
  }
  return excerpt(collapseWhitespace(parts.join(' ')));
}

async function fetchTranscriptExcerpt(
  track: CaptionTrack | null,
  fetchImpl: typeof fetch,
): Promise<string | null> {
  if (!track?.baseUrl) {
    return null;
  }
  try {
    const transcriptUrl = new URL(track.baseUrl);
    transcriptUrl.searchParams.set('fmt', 'json3');
    const response = await fetchImpl(transcriptUrl.toString(), {
      credentials: 'include',
    });
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as unknown;
    return transcriptSnippetFromJson3(payload);
  } catch {
    return null;
  }
}

function extractChannelUrlFromHtml(html: string, baseUrl: string): string | null {
  const ownerProfileMatch = html.match(/"ownerProfileUrl":"([^"]+)"/);
  if (ownerProfileMatch?.[1]) {
    return normalizeAbsoluteUrl(decodeEscapedYoutubeString(ownerProfileMatch[1]), baseUrl);
  }

  const canonicalBaseMatch = html.match(/"canonicalBaseUrl":"([^"]+)"/);
  if (canonicalBaseMatch?.[1]) {
    return normalizeAbsoluteUrl(decodeEscapedYoutubeString(canonicalBaseMatch[1]), baseUrl);
  }

  const document = parseHtmlDocument(html);
  const domCandidate =
    document?.querySelector<HTMLAnchorElement>(
      'link[itemprop="url"], a[href^="/@"], a[href^="/channel/"], a[href^="/c/"], a[href^="/user/"]',
    )?.getAttribute('href') ?? null;
  return normalizeAbsoluteUrl(domCandidate, baseUrl);
}

function buildChannelVideosUrl(channelUrl: string | null): string | null {
  if (!channelUrl) {
    return null;
  }

  try {
    const url = new URL(channelUrl);
    const normalizedPath = url.pathname.replace(/\/+$/, '');
    if (!normalizedPath || normalizedPath === '/') {
      return null;
    }
    url.pathname = normalizedPath.endsWith('/videos') ? normalizedPath : `${normalizedPath}/videos`;
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    return null;
  }
}

function extractRecentChannelTitlesFromHtml(html: string): string[] {
  const titles: string[] = [];
  const seen = new Set<string>();
  const document = parseHtmlDocument(html);

  const pushTitle = (value: string | null | undefined) => {
    const normalized = collapseWhitespace(value);
    if (!normalized || normalized.length < 8 || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    titles.push(normalized);
  };

  document
    ?.querySelectorAll<HTMLAnchorElement>(
      'a#video-title-link, a#video-title, h3 a[href*="/watch"], ytd-rich-grid-media a[href*="/watch"]',
    )
    .forEach((anchor) => {
      pushTitle(anchor.textContent ?? anchor.getAttribute('title'));
    });

  if (titles.length < 3) {
    const anchorMatches = html.matchAll(
      /<a[^>]+id="video-title[^"]*"[^>]*>([\s\S]*?)<\/a>/g,
    );
    for (const match of anchorMatches) {
      pushTitle(stripHtmlTags(match[1]));
      if (titles.length >= 5) {
        break;
      }
    }
  }

  if (titles.length < 3) {
    const matches = html.matchAll(/"title"\s*:\s*\{"runs"\s*:\s*\[\{"text":"([^"]+)"/g);
    for (const match of matches) {
      pushTitle(decodeEscapedYoutubeString(match[1]));
      if (titles.length >= 5) {
        break;
      }
    }
  }

  return titles.slice(0, 5);
}

async function fetchChannelContext(
  channelUrl: string | null,
  fetchImpl: typeof fetch,
): Promise<string | null> {
  const videosUrl = buildChannelVideosUrl(channelUrl);
  if (!videosUrl) {
    return null;
  }

  try {
    const response = await fetchImpl(videosUrl, { credentials: 'include' });
    if (!response.ok) {
      return null;
    }
    const html = await response.text();
    const titles = extractRecentChannelTitlesFromHtml(html);
    if (titles.length === 0) {
      return null;
    }
    return `Recent public channel titles: ${titles.map((title) => `"${title}"`).join('; ')}`;
  } catch {
    return null;
  }
}

export async function fetchYouTubeWatchMetadata(
  linkUrl: string,
  fetchImpl: typeof fetch = fetch,
  initialChannelUrl: string | null = null,
): Promise<YouTubeWatchMetadata> {
  try {
    const baseUrl =
      typeof window !== 'undefined' ? window.location.href : 'https://www.youtube.com/';
    const absoluteUrl = new URL(linkUrl, baseUrl).toString();
    const response = await fetchImpl(absoluteUrl, { credentials: 'include' });
    if (!response.ok) {
      return {
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        transcriptAvailable: null,
        channelUrl: null,
        channelContext: null,
      };
    }

    const html = await response.text();
    const playerResponse = parsePlayerResponseFromHtml(html);
    const descriptionSnapshot = excerpt(
      collapseWhitespace(playerResponse?.videoDetails?.shortDescription),
    );
    const captionTrack = chooseCaptionTrack(playerResponse);
    const transcriptExcerpt = await fetchTranscriptExcerpt(captionTrack, fetchImpl);
    const transcriptAvailable =
      captionTrack === null ? false : transcriptExcerpt !== null ? true : null;
    const channelUrl =
      extractChannelUrlFromHtml(html, absoluteUrl) ?? normalizeAbsoluteUrl(initialChannelUrl, absoluteUrl);
    const channelContext = await fetchChannelContext(channelUrl, fetchImpl);
    return {
      descriptionSnapshot,
      transcriptExcerpt,
      transcriptAvailable,
      channelUrl,
      channelContext,
    };
  } catch {
    return {
      descriptionSnapshot: null,
      transcriptExcerpt: null,
      transcriptAvailable: null,
      channelUrl: null,
      channelContext: null,
    };
  }
}
