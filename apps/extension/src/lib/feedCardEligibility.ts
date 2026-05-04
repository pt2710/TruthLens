export type YouTubeVideoLinkKind = 'watch' | 'shorts' | 'other' | 'unknown';

const PROMOTED_CARD_SELECTOR = [
  'ytd-ad-slot-renderer',
  'ytd-display-ad-renderer',
  'ytd-promoted-video-renderer',
  'ytd-promoted-sparkles-web-renderer',
  'ytd-in-feed-ad-layout-renderer',
  'ytd-compact-promoted-video-renderer',
  '[data-truthlens-ad-fixture]',
].join(', ');

const SPONSORED_MARKERS = [
  'sponsored',
  'sponsoreret',
  'promoted',
  'annonce',
  'advertisement',
];

const EXTERNAL_CTA_MARKERS = [
  'visit site',
  'besøg website',
  'besog website',
  'learn more',
  'shop now',
  'sign up',
  'buy now',
  'køb nu',
  'kob nu',
];

function defaultBaseUrl(): string {
  return typeof window !== 'undefined' ? window.location.href : 'https://www.youtube.com/';
}

function normalizedCardText(card: HTMLElement): string {
  return (card.textContent ?? '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function containsAny(text: string, markers: readonly string[]): boolean {
  return markers.some((marker) => text.includes(marker));
}

function isYouTubeHost(hostname: string): boolean {
  const normalized = hostname.toLowerCase();
  return (
    normalized === 'youtu.be' ||
    normalized === 'youtube.com' ||
    normalized.endsWith('.youtube.com')
  );
}

function isFixtureSameOrigin(url: URL, base: URL): boolean {
  return !isYouTubeHost(base.hostname) && url.origin === base.origin;
}

function parseUrl(value: string | null, baseUrl = defaultBaseUrl()): { url: URL; base: URL } | null {
  if (!value) {
    return null;
  }
  try {
    const base = new URL(baseUrl);
    return {
      url: new URL(value, base),
      base,
    };
  } catch {
    return null;
  }
}

export function inferYouTubeVideoLinkKind(
  value: string | null,
  baseUrl = defaultBaseUrl(),
): YouTubeVideoLinkKind {
  const parsed = parseUrl(value, baseUrl);
  if (!parsed) {
    return 'unknown';
  }

  const { url, base } = parsed;
  const allowedHost = isYouTubeHost(url.hostname) || isFixtureSameOrigin(url, base);
  if (!allowedHost) {
    return 'other';
  }

  if (url.hostname.toLowerCase() === 'youtu.be' && url.pathname.split('/').filter(Boolean).length >= 1) {
    return 'watch';
  }

  if (url.pathname === '/watch' && url.searchParams.get('v')) {
    return 'watch';
  }

  if (url.pathname.startsWith('/shorts/') && url.pathname.split('/').filter(Boolean).length >= 2) {
    return 'shorts';
  }

  return 'other';
}

export function extractPrimaryCardLinkUrl(card: HTMLElement): string | null {
  const anchor = card.querySelector<HTMLAnchorElement>(
    [
      'a#thumbnail[href]',
      'a#video-title-link[href]',
      'a[href*="/watch"][href]',
      'a[href*="/shorts/"][href]',
    ].join(', '),
  );
  return anchor?.href || anchor?.getAttribute('href') || null;
}

export function isPromotedOrExternalAdCard(
  card: HTMLElement,
  linkUrl: string | null = extractPrimaryCardLinkUrl(card),
  baseUrl = defaultBaseUrl(),
): boolean {
  if (card.closest(PROMOTED_CARD_SELECTOR)) {
    return true;
  }

  const linkKind = inferYouTubeVideoLinkKind(linkUrl, baseUrl);
  const text = normalizedCardText(card);
  const hasSponsoredMarker = containsAny(text, SPONSORED_MARKERS);
  const hasExternalCta = containsAny(text, EXTERNAL_CTA_MARKERS);
  const hasExternalPrimaryLink = Boolean(linkUrl) && linkKind === 'other';

  return hasExternalPrimaryLink || (hasSponsoredMarker && hasExternalCta);
}

export function isScoreableYouTubeVideoCard(
  card: HTMLElement,
  linkUrl: string | null = extractPrimaryCardLinkUrl(card),
  baseUrl = defaultBaseUrl(),
): boolean {
  if (isPromotedOrExternalAdCard(card, linkUrl, baseUrl)) {
    return false;
  }

  const linkKind = inferYouTubeVideoLinkKind(linkUrl, baseUrl);
  return linkKind === 'watch' || linkKind === 'shorts';
}
