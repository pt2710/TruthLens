import type {
  ManualReportRequestedOutcome,
  ManualReportWorkflowMode,
} from '@truthlens/shared-schemas';

export const MANUAL_REVIEW_SUBMITTED_EVENT = 'truthlens:manual-review-submitted';

export type ManualReviewSubmittedTarget = {
  itemId: string;
  channelName: string | null;
  linkUrl: string | null;
  thumbnailRef: string | null;
};

export type ManualReviewSubmittedDetail = {
  workflowMode: ManualReportWorkflowMode;
  userAction: string;
  requestedOutcome: ManualReportRequestedOutcome;
  targets: ManualReviewSubmittedTarget[];
};

type ManualReviewSubmittedHandler = (detail: ManualReviewSubmittedDetail) => void;
type TruthLensManualReviewWindow = Window & {
  __truthlensManualReviewSubmittedHandler?: ManualReviewSubmittedHandler;
};

function manualReviewWindow(): TruthLensManualReviewWindow {
  return window as TruthLensManualReviewWindow;
}

function normalizeComparableUrl(value: string | null): string | null {
  if (!value) {
    return null;
  }

  try {
    const url = new URL(value, window.location.href);
    if (url.pathname === '/watch') {
      const videoId = url.searchParams.get('v');
      return videoId ? `/watch?v=${videoId}` : url.pathname;
    }
    if (url.pathname.startsWith('/shorts/')) {
      return url.pathname;
    }
    return url.toString();
  } catch {
    return value;
  }
}

function normalizeAssetUrl(value: string | null): string | null {
  if (!value) {
    return null;
  }

  try {
    const url = new URL(value, window.location.href);
    url.search = '';
    return url.toString();
  } catch {
    return value;
  }
}

function suppressSubmittedReportTargets(detail: ManualReviewSubmittedDetail): void {
  if (detail.workflowMode !== 'report') {
    return;
  }

  const cards = Array.from(
    document.querySelectorAll<HTMLElement>(
      'ytd-rich-item-renderer, ytd-video-renderer, [data-truthlens-card]',
    ),
  );

  detail.targets.forEach((target) => {
    const normalizedTargetLink = normalizeComparableUrl(target.linkUrl);
    const normalizedTargetThumbnail = normalizeAssetUrl(target.thumbnailRef);
    const card = cards.find((candidate) => {
      const itemIdMatch = candidate.getAttribute('data-truthlens-item-id') === target.itemId;
      const linkUrl =
        candidate.querySelector<HTMLAnchorElement>(
          'a#thumbnail, a[href*="watch"], a[href*="/shorts/"], a[href*="playlist?list="]',
        )?.href ?? null;
      const thumbnailRef =
        candidate.querySelector<HTMLImageElement>('img')?.getAttribute('src') ?? null;
      const linkMatch =
        normalizedTargetLink !== null &&
        normalizeComparableUrl(linkUrl) === normalizedTargetLink;
      const thumbnailMatch =
        normalizedTargetThumbnail !== null &&
        normalizeAssetUrl(thumbnailRef) === normalizedTargetThumbnail;
      return itemIdMatch || linkMatch || thumbnailMatch;
    });

    if (!card) {
      return;
    }
    card.classList.add('truthlens-card-hidden', 'truthlens-card-suppressed');
    card.setAttribute('data-truthlens-suppressed', detail.userAction);
    card.setAttribute('aria-hidden', 'true');
  });
}

export function registerManualReviewSubmittedHandler(
  handler: ManualReviewSubmittedHandler,
): void {
  manualReviewWindow().__truthlensManualReviewSubmittedHandler = handler;
}

export function dispatchManualReviewSubmitted(
  detail: ManualReviewSubmittedDetail,
): void {
  suppressSubmittedReportTargets(detail);
  const handler = manualReviewWindow().__truthlensManualReviewSubmittedHandler;
  if (handler) {
    handler(detail);
    return;
  }

  window.dispatchEvent(
    new CustomEvent<ManualReviewSubmittedDetail>(MANUAL_REVIEW_SUBMITTED_EVENT, {
      detail,
    }),
  );
}
