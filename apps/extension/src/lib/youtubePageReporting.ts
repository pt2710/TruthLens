import type { ManualReportIssueType } from '@truthlens/shared-schemas';

import type { ManualReportTarget } from '../overlay/store';

const CARD_SELECTORS = ['ytd-rich-item-renderer', 'ytd-video-renderer', '[data-truthlens-card]'];
const WATCH_PAGE_ACTION_ROOT_SELECTORS = [
  'ytd-watch-metadata #actions',
  'ytd-watch-metadata #actions-inner',
  'ytd-watch-metadata #top-level-buttons-computed',
  'ytd-watch-metadata #menu',
  'ytd-watch-metadata ytd-menu-renderer',
  '#above-the-fold ytd-watch-metadata',
  'ytd-watch-flexy ytd-watch-metadata',
  'ytd-reel-player-overlay-renderer #actions',
  'ytd-reel-player-overlay-renderer ytd-menu-renderer',
];
const MENU_SURFACE_SELECTORS = [
  'tp-yt-iron-dropdown',
  'ytd-menu-popup-renderer',
  'tp-yt-paper-listbox[role="menu"]',
  '[role="menu"]',
];
const MENU_ITEM_SELECTORS = ['ytd-menu-service-item-renderer', 'tp-yt-paper-item', '[role="menuitem"]'];
const DIALOG_SELECTORS = ['tp-yt-paper-dialog', '[role="dialog"]', 'ytd-popup-container tp-yt-paper-dialog'];
const OPTION_SELECTORS = ['tp-yt-paper-radio-button', '[role="radio"]', 'tp-yt-paper-item', 'button'];
const BUTTON_SELECTORS = ['button', '[role="button"]'];
const MENU_ITEM_TIMEOUT_MS = 2500;
const REPORT_DIALOG_INITIAL_TIMEOUT_MS = 1500;
const REPORT_DIALOG_RETRY_TIMEOUT_MS = 4500;
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
      const listId = url.searchParams.get('list');
      if (!videoId) {
        return url.pathname;
      }
      return listId ? `/watch?v=${videoId}&list=${listId}` : `/watch?v=${videoId}`;
    }
    if (url.pathname.startsWith('/shorts/')) {
      return url.pathname;
    }
    if (url.pathname === '/playlist') {
      const listId = url.searchParams.get('list');
      return listId ? `/playlist?list=${listId}` : url.pathname;
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

function dedupeElements(elements: HTMLElement[]): HTMLElement[] {
  return Array.from(new Set(elements));
}

function matchesKeywordGroups(value: string, keywordGroups: string[][]): boolean {
  return keywordGroups.some((keywordGroup) => keywordGroup.every((keyword) => value.includes(keyword)));
}

function resolvesToReportHistory(element: HTMLElement): boolean {
  const href =
    element.getAttribute('href') ??
    element.closest<HTMLAnchorElement>('a[href]')?.getAttribute('href') ??
    null;
  if (!href) {
    return false;
  }

  return normalizeComparableUrl(href)?.includes('/reporthistory') ?? false;
}

function isEligibleReportMenuItem(element: HTMLElement): boolean {
  const text = getVisibleText(element);
  if (!text || !matchesKeywordGroups(text, REPORT_MENU_ITEM_KEYWORD_GROUPS)) {
    return false;
  }

  if (resolvesToReportHistory(element)) {
    return false;
  }

  if (
    text.includes('report history') ||
    text.includes('reporthistory') ||
    text.includes('rapporthistor') ||
    text.includes('anmeld histor') ||
    text.includes('historik')
  ) {
    return false;
  }

  return true;
}

function buildAvailableLabelSummary(elements: HTMLElement[]): string {
  const labels = elements
    .map((element) => getVisibleText(element))
    .filter(Boolean)
    .map((label) => label.replace(/\s+/g, ' ').trim());
  return labels.join(', ') || 'none';
}

function clickElement(element: HTMLElement): void {
  element.scrollIntoView?.({ block: 'center', inline: 'center' });
  element.focus?.({ preventScroll: true });
  if (typeof element.click === 'function') {
    element.click();
    return;
  }
  element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
}

function elementCenterDistance(from: HTMLElement, to: HTMLElement): number {
  const fromRect = from.getBoundingClientRect();
  const toRect = to.getBoundingClientRect();
  const fromX = fromRect.left + fromRect.width / 2;
  const fromY = fromRect.top + fromRect.height / 2;
  const toX = toRect.left + toRect.width / 2;
  const toY = toRect.top + toRect.height / 2;
  return Math.hypot(fromX - toX, fromY - toY);
}

function findVisibleMenuRoots(menuButton?: HTMLElement): HTMLElement[] {
  const roots = dedupeElements(
    collectVisibleElements(MENU_SURFACE_SELECTORS).filter((root) =>
      root.querySelector(MENU_ITEM_SELECTORS.join(',')),
    ),
  );

  if (!menuButton) {
    return roots.reverse();
  }

  return roots.sort((left, right) => {
    const distanceDelta = elementCenterDistance(menuButton, left) - elementCenterDistance(menuButton, right);
    if (distanceDelta !== 0) {
      return distanceDelta;
    }
    return left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING ? 1 : -1;
  });
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
  options: { timeoutMs?: number; intervalMs?: number; errorMessage?: string } = {},
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
      throw new Error(options.errorMessage ?? 'Timed out while waiting for YouTube to show the report UI.');
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

function findVisibleWatchPageRoot(): HTMLElement | null {
  const candidates = [
    'ytd-watch-metadata',
    '#above-the-fold',
    '#primary-inner',
    'ytd-watch-flexy',
    'ytd-reel-video-renderer',
    'ytd-shorts',
  ];
  return (
    candidates
      .map((selector) => document.querySelector<HTMLElement>(selector))
      .find((element) => isVisible(element ?? null)) ?? null
  );
}

function findMenuButtons(root: ParentNode): HTMLElement[] {
  const candidates = Array.from(
    root.querySelectorAll<HTMLElement>(
      [
        'ytd-menu-renderer button',
        '#menu button',
        'button[aria-label]',
        'yt-icon-button button',
        'tp-yt-paper-icon-button',
      ].join(','),
    ),
  );

  const preferredButtons = candidates.filter((candidate) => {
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
  });

  if (preferredButtons.length > 0) {
    return dedupeElements(preferredButtons);
  }

  return dedupeElements(candidates.filter((candidate) => !candidate.closest('.truthlens-action-row')));
}

function findMenuButton(root: ParentNode): HTMLElement | null {
  return findMenuButtons(root)[0] ?? null;
}

function findWatchPageMenuButtons(): HTMLElement[] {
  const actionRoots = dedupeElements(
    WATCH_PAGE_ACTION_ROOT_SELECTORS.map((selector) =>
      document.querySelector<HTMLElement>(selector),
    ).filter((element): element is HTMLElement => isVisible(element)),
  );
  const actionButtons = dedupeElements(actionRoots.flatMap((root) => findMenuButtons(root)));
  if (actionButtons.length > 0) {
    return actionButtons;
  }

  const watchRoot = findVisibleWatchPageRoot();
  if (!watchRoot) {
    return [];
  }

  return findMenuButtons(watchRoot);
}

type ManualReportSurface =
  | {
      surfaceLabel: 'current page card';
      menuButtons: [HTMLElement];
    }
  | {
      surfaceLabel: 'watch page';
      menuButtons: HTMLElement[];
    };

function collectVisibleMenuItemsFromRoots(roots: HTMLElement[]): HTMLElement[] {
  return dedupeElements(roots.flatMap((root) => collectVisibleElements(MENU_ITEM_SELECTORS, root)));
}

async function waitForOpenedMenuRoots(
  menuButton: HTMLElement,
  previouslyVisibleRoots: Set<HTMLElement>,
): Promise<HTMLElement[] | null> {
  return waitFor(() => {
    const visibleRoots = findVisibleMenuRoots(menuButton);
    const newlyVisibleRoots = visibleRoots.filter((root) => !previouslyVisibleRoots.has(root));
    return newlyVisibleRoots.length > 0 ? newlyVisibleRoots : null;
  }, {
    timeoutMs: MENU_ITEM_TIMEOUT_MS,
  }).catch(() => null);
}

function findManualReportSurface(target: ManualReportTarget): ManualReportSurface | null {
  const card = findManualReportCard(target);
  if (card) {
    const menuButton = findMenuButton(card);
    if (menuButton) {
      return { surfaceLabel: 'current page card', menuButtons: [menuButton] };
    }
  }

  const menuButtons = findWatchPageMenuButtons();
  if (menuButtons.length === 0) {
    return null;
  }

  return { surfaceLabel: 'watch page', menuButtons };
}

function findVisibleDialog(): HTMLElement | null {
  return collectVisibleElements(DIALOG_SELECTORS)[0] ?? null;
}

function findVisibleMenuItem(keywordGroups: string[][], menuButton?: HTMLElement): HTMLElement | null {
  const menuRoots = findVisibleMenuRoots(menuButton);
  if (menuRoots.length > 0) {
    for (const root of menuRoots) {
      const candidate = collectVisibleElements(MENU_ITEM_SELECTORS, root).find((element) =>
        keywordGroups === REPORT_MENU_ITEM_KEYWORD_GROUPS
          ? isEligibleReportMenuItem(element)
          : matchesKeywordGroups(getVisibleText(element), keywordGroups),
      );
      if (candidate) {
        return candidate;
      }
    }
    return null;
  }

  return (
    collectVisibleElements(MENU_ITEM_SELECTORS).find((element) =>
      keywordGroups === REPORT_MENU_ITEM_KEYWORD_GROUPS
        ? isEligibleReportMenuItem(element)
        : matchesKeywordGroups(getVisibleText(element), keywordGroups),
    ) ?? null
  );
}

function findVisibleReportMenuCandidates(
  menuButton: HTMLElement,
  excludedCandidates: Set<HTMLElement> = new Set(),
  previouslyVisibleRoots: Set<HTMLElement> = new Set(),
): HTMLElement[] {
  const roots = findVisibleMenuRoots(menuButton);
  const prioritizedRoots = [
    ...roots.filter((root) => !previouslyVisibleRoots.has(root)),
    ...roots.filter((root) => previouslyVisibleRoots.has(root)),
  ];

  for (const root of prioritizedRoots) {
    const candidates = collectVisibleElements(MENU_ITEM_SELECTORS, root).filter(
      (element) => isEligibleReportMenuItem(element) && !excludedCandidates.has(element),
    );
    if (candidates.length > 0) {
      return candidates;
    }
  }

  return [];
}

async function waitForVisibleReportMenuCandidates(
  menuButton: HTMLElement,
  excludedCandidates: Set<HTMLElement> = new Set(),
  previouslyVisibleRoots: Set<HTMLElement> = new Set(),
): Promise<HTMLElement[]> {
  return waitFor(() => {
    const candidates = findVisibleReportMenuCandidates(
      menuButton,
      excludedCandidates,
      previouslyVisibleRoots,
    );
    return candidates.length > 0 ? candidates : null;
  }, {
    timeoutMs: MENU_ITEM_TIMEOUT_MS,
  });
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

async function waitForReportDialog(
  menuButton: HTMLElement,
  reportMenuItem: HTMLElement,
): Promise<HTMLElement> {
  const dialogErrorMessage =
    'TruthLens found YouTube’s "Report" menu entry, but YouTube did not open the report dialog in time.';
  const tryWaitForDialog = async (timeoutMs: number): Promise<HTMLElement | null> =>
    waitFor(() => findVisibleDialog(), {
      timeoutMs,
      errorMessage: dialogErrorMessage,
    }).catch(() => null);

  clickElement(reportMenuItem);
  let dialog = await tryWaitForDialog(REPORT_DIALOG_INITIAL_TIMEOUT_MS);
  if (dialog) {
    return dialog;
  }

  const repeatedMenuItem = findVisibleMenuItem(REPORT_MENU_ITEM_KEYWORD_GROUPS, menuButton);
  if (repeatedMenuItem) {
    clickElement(repeatedMenuItem);
    dialog = await tryWaitForDialog(REPORT_DIALOG_INITIAL_TIMEOUT_MS);
    if (dialog) {
      return dialog;
    }
  }

  const visibleRootsBeforeRetry = new Set(findVisibleMenuRoots(menuButton));
  clickElement(menuButton);
  const retryCandidates = await waitForVisibleReportMenuCandidates(
    menuButton,
    new Set([reportMenuItem, repeatedMenuItem].filter((candidate): candidate is HTMLElement => Boolean(candidate))),
    visibleRootsBeforeRetry,
  ).catch(() => []);
  for (const retryCandidate of retryCandidates) {
    clickElement(retryCandidate);
    dialog = await tryWaitForDialog(REPORT_DIALOG_RETRY_TIMEOUT_MS);
    if (dialog) {
      return dialog;
    }
  }

  throw new Error(dialogErrorMessage);
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

export async function submitYouTubePageReportInDocument(
  target: ManualReportTarget,
  issueTypes: ManualReportIssueType[],
): Promise<YouTubePageReportResult> {
  const surface = findManualReportSurface(target);
  if (!surface) {
    throw new Error(
      'TruthLens could not find a usable YouTube report surface for this video on the current document.',
    );
  }

  let reportMenuItem: HTMLElement | null = null;
  let menuButton: HTMLElement | null = null;
  let availableMenuItems: HTMLElement[] = [];

  if (surface.surfaceLabel === 'current page card') {
    menuButton = surface.menuButtons[0];
    const visibleRootsBeforeMenuOpen = new Set(findVisibleMenuRoots(menuButton));
    clickElement(menuButton);
    const reportMenuCandidates = await waitForVisibleReportMenuCandidates(
      menuButton,
      new Set(),
      visibleRootsBeforeMenuOpen,
    ).catch(() => []);
    reportMenuItem = reportMenuCandidates[0] ?? null;
    if (!reportMenuItem) {
      availableMenuItems = collectVisibleElements(MENU_ITEM_SELECTORS);
    }
  } else {
    for (const candidateMenuButton of surface.menuButtons) {
      const visibleRootsBeforeMenuOpen = new Set(findVisibleMenuRoots(candidateMenuButton));
      clickElement(candidateMenuButton);
      const openedMenuRoots = await waitForOpenedMenuRoots(
        candidateMenuButton,
        visibleRootsBeforeMenuOpen,
      );
      if (!openedMenuRoots) {
        continue;
      }

      availableMenuItems = collectVisibleMenuItemsFromRoots(openedMenuRoots);
      reportMenuItem =
        findVisibleReportMenuCandidates(
          candidateMenuButton,
          new Set(),
          visibleRootsBeforeMenuOpen,
        )[0] ?? null;
      if (reportMenuItem) {
        menuButton = candidateMenuButton;
        break;
      }
    }
  }

  if (!reportMenuItem) {
    throw new Error(
      `TruthLens could not find YouTube’s in-page "Report" option on the ${surface.surfaceLabel}. Available menu items: ` +
        buildAvailableLabelSummary(availableMenuItems) +
        '.',
    );
  }
  const dialog = await waitForReportDialog(menuButton ?? surface.menuButtons[0], reportMenuItem);
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

export async function submitYouTubePageReport(
  target: ManualReportTarget,
  issueTypes: ManualReportIssueType[],
): Promise<YouTubePageReportResult> {
  return submitYouTubePageReportInDocument(target, issueTypes);
}
