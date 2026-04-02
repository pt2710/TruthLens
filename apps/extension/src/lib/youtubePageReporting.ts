import type { ManualReportIssueType } from '@truthlens/shared-schemas';

import type { ManualReportTarget } from '../overlay/store';

const CARD_SELECTORS = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
const MENU_ITEM_SELECTORS = ['ytd-menu-service-item-renderer', 'tp-yt-paper-item', '[role="menuitem"]'];
const DIALOG_SELECTORS = ['tp-yt-paper-dialog', '[role="dialog"]', 'ytd-popup-container tp-yt-paper-dialog'];
const OPTION_SELECTORS = ['tp-yt-paper-radio-button', '[role="radio"]', 'tp-yt-paper-item', 'button'];
const BUTTON_SELECTORS = ['button', '[role="button"]'];
const REPORT_MENU_ITEM_KEYWORD_GROUPS = [['report'], ['rapport'], ['anmeld']];
const PRIMARY_REASON_KEYWORD_GROUPS = [
  ['spam', 'misleading'],
  ['misleading'],
  ['deceptive'],
  ['clickbait'],
  ['vildled'],
];
const NEXT_BUTTON_KEYWORD_GROUPS = [
  ['next'],
  ['continue'],
  ['naeste'],
  ['næste'],
  ['videre'],
  ['fortsaet'],
  ['fortsæt'],
];
const SUBMIT_BUTTON_KEYWORD_GROUPS = [
  ['submit'],
  ['send'],
  ['report'],
  ['indsend'],
  ['anmeld'],
  ['udfor'],
  ['rapporter'],
  ['faerdig'],
  ['færdig'],
];

export type YouTubePageReportResult = {
  status: 'reported';
  reason_label: string;
  secondary_reason_label: string | null;
};

function normalizeText(value: string | null | undefined): string {
  return (value ?? '')
    .normalize('NFKD')
    .replace(/æ/g, 'ae')
    .replace(/ø/g, 'oe')
    .replace(/å/g, 'aa')
    .replace(/Æ/g, 'ae')
    .replace(/Ø/g, 'oe')
    .replace(/Å/g, 'aa')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
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

function isVisible(element: Element | null): element is HTMLElement {
  if (!(element instanceof HTMLElement)) {
    return false;
  }

  let current: HTMLElement | null = element;
  while (current) {
    const style = window.getComputedStyle(current);
    if (current.hidden || style.display === 'none' || style.visibility === 'hidden') {
      return false;
    }
    current = current.parentElement;
  }

  return true;
}

function getVisibleText(element: Element | null): string {
  if (!(element instanceof HTMLElement)) {
    return '';
  }
  return normalizeText(element.innerText || element.textContent || '');
}

function collectVisibleElements(selectors: string[], root: ParentNode = document): HTMLElement[] {
  return selectors.flatMap((selector) =>
    Array.from(root.querySelectorAll(selector)).filter((element): element is HTMLElement =>
      isVisible(element),
    ),
  );
}

function matchesKeywordGroups(value: string, keywordGroups: string[][]): boolean {
  return keywordGroups.some((keywordGroup) => keywordGroup.every((keyword) => value.includes(keyword)));
}

function buildAvailableLabelSummary(elements: HTMLElement[]): string {
  const labels = elements
    .map((element) => getVisibleText(element))
    .filter(Boolean)
    .map((label) => label.replace(/\s+/g, ' ').trim());
  return labels.join(', ') || 'none';
}

function clickElement(element: HTMLElement): void {
  element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
}

function isDisabled(element: HTMLElement): boolean {
  return (
    element.hasAttribute('disabled') ||
    element.getAttribute('aria-disabled') === 'true' ||
    element.getAttribute('tabindex') === '-1'
  );
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function waitFor<T>(
  factory: () => T | null,
  options: { timeoutMs?: number; intervalMs?: number } = {},
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? 2500;
  const intervalMs = options.intervalMs ?? 50;
  const startedAt = Date.now();

  for (;;) {
    const value = factory();
    if (value !== null) {
      return value;
    }
    if (Date.now() - startedAt >= timeoutMs) {
      throw new Error('Timed out while waiting for YouTube to show the report UI.');
    }
    await sleep(intervalMs);
  }
}

function findManualReportCard(target: ManualReportTarget): HTMLElement | null {
  const normalizedLink = normalizeComparableUrl(target.linkUrl);
  const normalizedThumbnail = normalizeAssetUrl(target.thumbnailRef);
  const normalizedTitle = normalizeText(target.title);
  const normalizedChannel = normalizeText(target.channelName);

  const cards = Array.from(document.querySelectorAll<HTMLElement>(CARD_SELECTORS.join(',')));
  for (const card of cards) {
    const linkUrl =
      card.querySelector<HTMLAnchorElement>('a#thumbnail, a[href*="watch"], a[href*="/shorts/"]')
        ?.href || null;
    const thumbnailRef = card.querySelector<HTMLImageElement>('img')?.getAttribute('src') || null;
    const title = normalizeText(
      card.querySelector<HTMLElement>('#video-title, h3, a[title]')?.textContent ?? '',
    );
    const channel = normalizeText(
      card.querySelector<HTMLElement>('ytd-channel-name, #channel-name, [id="channel-info"] a')
        ?.textContent ?? '',
    );

    if (normalizedLink && normalizeComparableUrl(linkUrl) === normalizedLink) {
      return card;
    }
    if (normalizedThumbnail && normalizeAssetUrl(thumbnailRef) === normalizedThumbnail) {
      return card;
    }
    if (title === normalizedTitle && channel === normalizedChannel) {
      return card;
    }
  }

  return null;
}

function findMenuButton(card: HTMLElement): HTMLElement | null {
  const candidates = Array.from(
    card.querySelectorAll<HTMLElement>(
      [
        'ytd-menu-renderer button',
        '#menu button',
        'button[aria-label]',
        'yt-icon-button button',
        'tp-yt-paper-icon-button',
      ].join(','),
    ),
  );

  return (
    candidates.find((candidate) => {
      if (candidate.closest('.truthlens-action-row')) {
        return false;
      }
      const label = getVisibleText(candidate);
      return (
        label.includes('action menu') ||
        label.includes('more') ||
        label.includes('handlingsmenu') ||
        label.includes('menu')
      );
    }) ?? candidates.find((candidate) => !candidate.closest('.truthlens-action-row')) ?? null
  );
}

function findVisibleDialog(): HTMLElement | null {
  return collectVisibleElements(DIALOG_SELECTORS)[0] ?? null;
}

function findVisibleMenuItem(keywordGroups: string[][]): HTMLElement | null {
  return (
    collectVisibleElements(MENU_ITEM_SELECTORS).find((element) =>
      matchesKeywordGroups(getVisibleText(element), keywordGroups),
    ) ?? null
  );
}

function findOption(
  root: ParentNode,
  keywordGroups: string[][],
  excludedKeywordGroups: string[][] = [],
): HTMLElement | null {
  const candidates = collectVisibleElements(OPTION_SELECTORS, root).filter((element) => {
    const text = getVisibleText(element);
    if (!text) {
      return false;
    }
    if (excludedKeywordGroups.some((keywords) => matchesKeywordGroups(text, [keywords]))) {
      return false;
    }
    return !element.classList.contains('truthlens-action-button');
  });

  return candidates.find((candidate) => matchesKeywordGroups(getVisibleText(candidate), keywordGroups)) ?? null;
}

function findButton(root: ParentNode, keywordGroups: string[][]): HTMLElement | null {
  const candidates = collectVisibleElements(BUTTON_SELECTORS, root).filter(
    (element) => !element.classList.contains('truthlens-action-button') && !isDisabled(element),
  );

  return candidates.find((candidate) => matchesKeywordGroups(getVisibleText(candidate), keywordGroups)) ?? null;
}

function findFallbackSelectableOption(root: ParentNode): HTMLElement | null {
  const candidates = collectVisibleElements(OPTION_SELECTORS, root).filter((element) => {
    if (element.classList.contains('truthlens-action-button') || isDisabled(element)) {
      return false;
    }

    const text = getVisibleText(element);
    if (!text) {
      return false;
    }

    return !matchesKeywordGroups(text, [...NEXT_BUTTON_KEYWORD_GROUPS, ...SUBMIT_BUTTON_KEYWORD_GROUPS]);
  });

  return candidates[0] ?? null;
}

function buildSecondaryReasonKeywordGroups(issueTypes: ManualReportIssueType[]): string[][] {
  const issueSet = new Set(issueTypes);
  if (issueSet.size === 1 && issueSet.has('thumbnail')) {
    return [['misleading', 'thumbnail'], ['thumbnail'], ['miniature']];
  }

  const groups: string[][] = [
    ['other', 'misleading'],
    ['misleading', 'info'],
    ['metadata'],
    ['clickbait'],
  ];
  if (issueSet.has('thumbnail')) {
    groups.push(['misleading', 'thumbnail'], ['thumbnail'], ['miniature']);
  }
  return groups;
}

async function advanceDialog(
  issueTypes: ManualReportIssueType[],
): Promise<{ secondaryReasonLabel: string | null }> {
  let secondaryReasonLabel: string | null = null;
  let attemptedFallbackSelection = false;

  for (let attempt = 0; attempt < 10; attempt += 1) {
    await sleep(150);
    const dialog = findVisibleDialog();
    if (!dialog) {
      return { secondaryReasonLabel };
    }

    const secondaryOption = findOption(
      dialog,
      buildSecondaryReasonKeywordGroups(issueTypes),
      [...NEXT_BUTTON_KEYWORD_GROUPS, ...SUBMIT_BUTTON_KEYWORD_GROUPS],
    );
    if (secondaryOption && secondaryReasonLabel === null) {
      secondaryReasonLabel =
        secondaryOption.getAttribute('aria-label')?.trim() ||
        secondaryOption.textContent?.trim() ||
        null;
      clickElement(secondaryOption);
      attemptedFallbackSelection = false;
      continue;
    }

    const submitButton = findButton(dialog, SUBMIT_BUTTON_KEYWORD_GROUPS);
    if (submitButton) {
      clickElement(submitButton);
      try {
        await waitFor(() => (findVisibleDialog() ? null : true), { timeoutMs: 1500 });
        return { secondaryReasonLabel };
      } catch {
        // Some YouTube variants stay mounted briefly or require an option selection first.
      }
    }

    const nextButton = findButton(dialog, NEXT_BUTTON_KEYWORD_GROUPS);
    if (nextButton) {
      clickElement(nextButton);
      continue;
    }

    const fallbackOption = findFallbackSelectableOption(dialog);
    if (fallbackOption && !attemptedFallbackSelection) {
      if (secondaryReasonLabel === null) {
        secondaryReasonLabel =
          fallbackOption.getAttribute('aria-label')?.trim() ||
          fallbackOption.textContent?.trim() ||
          null;
      }
      clickElement(fallbackOption);
      attemptedFallbackSelection = true;
      continue;
    }
  }

  const dialog = findVisibleDialog();
  const availableOptions = dialog ? collectVisibleElements(OPTION_SELECTORS, dialog) : [];
  const availableButtons = dialog ? collectVisibleElements(BUTTON_SELECTORS, dialog) : [];
  throw new Error(
    'TruthLens found the YouTube report dialog but could not finish the in-page report flow. ' +
      'Visible options: ' +
      buildAvailableLabelSummary(availableOptions) +
      '. Visible buttons: ' +
      buildAvailableLabelSummary(availableButtons) +
      '.',
  );
}

export async function submitYouTubePageReport(
  target: ManualReportTarget,
  issueTypes: ManualReportIssueType[],
): Promise<YouTubePageReportResult> {
  const card = findManualReportCard(target);
  if (!card) {
    throw new Error('TruthLens could not find the selected YouTube card on the current page.');
  }

  const menuButton = findMenuButton(card);
  if (!menuButton) {
    throw new Error(
      'TruthLens could not find YouTube’s action menu on this card. Make sure you are signed in and the card is visible.',
    );
  }
  clickElement(menuButton);

  const reportMenuItem = await waitFor(() => findVisibleMenuItem(REPORT_MENU_ITEM_KEYWORD_GROUPS), {
    timeoutMs: 2500,
  }).catch(() => null);
  if (!reportMenuItem) {
    const availableMenuItems = collectVisibleElements(MENU_ITEM_SELECTORS);
    throw new Error(
      'TruthLens could not find YouTube’s in-page "Report" option on this card. Available menu items: ' +
        buildAvailableLabelSummary(availableMenuItems) +
        '.',
    );
  }
  clickElement(reportMenuItem);

  const dialog = await waitFor(() => findVisibleDialog(), { timeoutMs: 2500 });
  const primaryReason = findOption(
    dialog,
    PRIMARY_REASON_KEYWORD_GROUPS,
    [...NEXT_BUTTON_KEYWORD_GROUPS, ...SUBMIT_BUTTON_KEYWORD_GROUPS],
  );
  if (!primaryReason) {
    const availableReasons = collectVisibleElements(OPTION_SELECTORS, dialog);
    throw new Error(
      'TruthLens opened the YouTube report dialog, but it could not find a misleading/spam option there. Available options: ' +
        buildAvailableLabelSummary(availableReasons) +
        '.',
    );
  }

  const reasonLabel =
    primaryReason.getAttribute('aria-label')?.trim() || primaryReason.textContent?.trim() || 'Spam or misleading';
  clickElement(primaryReason);
  const { secondaryReasonLabel } = await advanceDialog(issueTypes);

  return {
    status: 'reported',
    reason_label: reasonLabel,
    secondary_reason_label: secondaryReasonLabel,
  };
}
