// @vitest-environment jsdom

import { afterEach, describe, expect, it } from 'vitest';

import {
  extractPrimaryCardLinkUrl,
  inferYouTubeVideoLinkKind,
  isPromotedOrExternalAdCard,
  isScoreableYouTubeVideoCard,
} from './feedCardEligibility';

function renderCard(html: string): HTMLElement {
  document.body.innerHTML = html;
  const card = document.querySelector<HTMLElement>('[data-truthlens-card], ytd-ad-slot-renderer');
  if (!card) {
    throw new Error('Expected fixture card.');
  }
  return card;
}

describe('feed card eligibility', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('rejects sponsored external website ad cards', () => {
    const card = renderCard(`
      <article data-truthlens-card>
        <a id="thumbnail" href="https://www.starlink.com/residential">
          <img alt="Starlink ad" src="https://example.com/starlink.jpg" />
        </a>
        <p>Sponsoreret · Starlink</p>
        <h3>High-speed internet around the world</h3>
        <a href="https://www.starlink.com/residential">Besøg website</a>
      </article>
    `);

    expect(extractPrimaryCardLinkUrl(card)).toContain('starlink.com');
    expect(isPromotedOrExternalAdCard(card)).toBe(true);
    expect(isScoreableYouTubeVideoCard(card)).toBe(false);
  });

  it('rejects promoted renderer cards even when their copy looks like a feed item', () => {
    const card = renderCard(`
      <ytd-ad-slot-renderer data-truthlens-card>
        <a id="thumbnail" href="https://www.youtube.com/redirect?event=ad&q=https%3A%2F%2Fexample.com">
          <img alt="promoted thumbnail" src="https://example.com/ad.jpg" />
        </a>
        <h3 id="video-title">Promoted launch recap</h3>
        <span>Sponsored</span>
        <button>Visit site</button>
      </ytd-ad-slot-renderer>
    `);

    expect(inferYouTubeVideoLinkKind(extractPrimaryCardLinkUrl(card))).toBe('other');
    expect(isPromotedOrExternalAdCard(card)).toBe(true);
    expect(isScoreableYouTubeVideoCard(card)).toBe(false);
  });

  it('allows normal YouTube watch feed cards', () => {
    const card = renderCard(`
      <article data-truthlens-card>
        <a id="thumbnail" href="/watch?v=fixture-item-1">
          <img alt="video thumbnail" src="https://example.com/video.jpg" />
        </a>
        <h3 id="video-title">Weekly launch schedule and mission recap</h3>
        <p>Routine video metadata.</p>
      </article>
    `);

    expect(inferYouTubeVideoLinkKind(extractPrimaryCardLinkUrl(card))).toBe('watch');
    expect(isPromotedOrExternalAdCard(card)).toBe(false);
    expect(isScoreableYouTubeVideoCard(card)).toBe(true);
  });

  it('allows normal YouTube shorts feed cards', () => {
    const card = renderCard(`
      <article data-truthlens-card>
        <a id="thumbnail" href="/shorts/fixture-short-1">
          <img alt="short thumbnail" src="https://example.com/short.jpg" />
        </a>
        <h3 id="video-title">Transparent short update</h3>
      </article>
    `);

    expect(inferYouTubeVideoLinkKind(extractPrimaryCardLinkUrl(card))).toBe('shorts');
    expect(isScoreableYouTubeVideoCard(card)).toBe(true);
  });

  it('does not reject a normal video merely because description text mentions a website', () => {
    const card = renderCard(`
      <article data-truthlens-card>
        <a id="thumbnail" href="/watch?v=fixture-item-2">
          <img alt="video thumbnail" src="https://example.com/video.jpg" />
        </a>
        <h3 id="video-title">Creator update with website resources</h3>
        <p>Links on the website are discussed in the video.</p>
      </article>
    `);

    expect(isPromotedOrExternalAdCard(card)).toBe(false);
    expect(isScoreableYouTubeVideoCard(card)).toBe(true);
  });
});
