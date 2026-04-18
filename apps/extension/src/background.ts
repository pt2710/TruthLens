import { buildTruthLensApiUrl } from './lib/runtimeConfig';
import type { ManualReportIssueType } from '@truthlens/shared-schemas';
import type { ManualReportTarget } from './overlay/store';
import type { YouTubePageReportResult } from './lib/youtubePageReporting';

export const MANUAL_REPORT_MENU_ID = 'truthlens-manual-report';
export const VERIFY_TRANSPARENT_MENU_ID = 'truthlens-verify-transparent';
const BACKGROUND_REPORT_BOOT_DELAY_MS = 1200;
const BACKGROUND_REPORT_MESSAGE_RETRY_MS = 400;
const BACKGROUND_REPORT_MESSAGE_ATTEMPTS = 20;
const BACKGROUND_REPORT_ERROR_MESSAGE =
  'TruthLens could not complete the protected YouTube report flow without leaving the current page.';

type BackgroundPageReportMessage = {
  type: 'TRUTHLENS_SUBMIT_PAGE_REPORT';
  target: ManualReportTarget;
  issueTypes: ManualReportIssueType[];
};

type ExecutePageReportMessage = {
  type: 'TRUTHLENS_EXECUTE_PAGE_REPORT';
  target: ManualReportTarget;
  issueTypes: ManualReportIssueType[];
};

type PageReportRuntimeResponse =
  | { ok: true; data: YouTubePageReportResult }
  | { ok: false; error?: string };

export function buildManualReportMenuOptions(): chrome.contextMenus.CreateProperties {
  return {
    id: MANUAL_REPORT_MENU_ID,
    title: 'Report video with TruthLens',
    contexts: ['image', 'link'],
    documentUrlPatterns: ['https://www.youtube.com/*'],
  };
}

export function buildTransparentVerificationMenuOptions(): chrome.contextMenus.CreateProperties {
  return {
    id: VERIFY_TRANSPARENT_MENU_ID,
    title: 'Verify transparent with TruthLens',
    contexts: ['image', 'link'],
    documentUrlPatterns: ['https://www.youtube.com/*'],
  };
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function submitPageReportInBackground(
  target: ManualReportTarget,
  issueTypes: ManualReportIssueType[],
): Promise<YouTubePageReportResult> {
  if (!target.linkUrl) {
    throw new Error('TruthLens could not determine a YouTube video URL for the protected report flow.');
  }

  const tab = await chrome.tabs.create({
    url: target.linkUrl,
    active: false,
  });
  if (typeof tab.id !== 'number') {
    throw new Error(BACKGROUND_REPORT_ERROR_MESSAGE);
  }

  const reportTabId = tab.id;
  await sleep(BACKGROUND_REPORT_BOOT_DELAY_MS);

  try {
    let lastError: string | null = null;
    const payload: ExecutePageReportMessage = {
      type: 'TRUTHLENS_EXECUTE_PAGE_REPORT',
      target,
      issueTypes,
    };

    for (let attempt = 0; attempt < BACKGROUND_REPORT_MESSAGE_ATTEMPTS; attempt += 1) {
      try {
        const response = (await chrome.tabs.sendMessage(
          reportTabId,
          payload,
        )) as PageReportRuntimeResponse | undefined;
        if (response?.ok) {
          return response.data;
        }
        lastError = response?.error ?? BACKGROUND_REPORT_ERROR_MESSAGE;
      } catch (error) {
        lastError = error instanceof Error ? error.message : BACKGROUND_REPORT_ERROR_MESSAGE;
      }

      await sleep(BACKGROUND_REPORT_MESSAGE_RETRY_MS);
    }

    throw new Error(lastError ?? BACKGROUND_REPORT_ERROR_MESSAGE);
  } finally {
    try {
      await chrome.tabs.remove(reportTabId);
    } catch {
      // Ignore cleanup failures for already-closed tabs.
    }
  }
}

function ensureContextMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create(buildManualReportMenuOptions());
    chrome.contextMenus.create(buildTransparentVerificationMenuOptions());
  });
}

if (typeof chrome !== 'undefined' && chrome.runtime?.onInstalled) {
  chrome.runtime.onInstalled.addListener(() => {
    ensureContextMenu();
  });

  chrome.runtime.onStartup?.addListener(() => {
    ensureContextMenu();
  });

  chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (
      (info.menuItemId !== MANUAL_REPORT_MENU_ID &&
        info.menuItemId !== VERIFY_TRANSPARENT_MENU_ID) ||
      typeof tab?.id !== 'number'
    ) {
      return;
    }

    void chrome.tabs.sendMessage(tab.id, {
      type: 'TRUTHLENS_OPEN_MANUAL_REPORT',
      linkUrl: info.linkUrl ?? null,
      srcUrl: info.srcUrl ?? null,
      pageUrl: info.pageUrl ?? null,
      workflowMode:
        info.menuItemId === VERIFY_TRANSPARENT_MENU_ID ? 'verify-transparent' : 'report',
    });
  });

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === 'TRUTHLENS_PING') {
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'TRUTHLENS_OPTIMIZE_MANUAL_REPORT') {
      void fetch(buildTruthLensApiUrl('/manual-report/optimize'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(message.payload),
      })
        .then(async (response) => {
          if (!response.ok) {
            let detail = `Manual report optimization failed: ${response.status}`;
            try {
              const payload = (await response.json()) as { detail?: string };
              if (payload.detail) {
                detail = payload.detail;
              }
            } catch {
              // Leave the default error text intact.
            }
            sendResponse({ ok: false, error: detail });
            return;
          }
          sendResponse({ ok: true, data: await response.json() });
        })
        .catch((error: unknown) => {
          sendResponse({
            ok: false,
            error:
              error instanceof Error
                ? error.message
                : 'Manual report optimization failed in the background worker.',
          });
        });
      return true;
    }

    if (message?.type === 'TRUTHLENS_OPEN_REPORT_TARGET' && typeof message.url === 'string') {
      chrome.tabs.create({ url: message.url });
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'TRUTHLENS_SUBMIT_PAGE_REPORT') {
      void submitPageReportInBackground(
        (message as BackgroundPageReportMessage).target,
        (message as BackgroundPageReportMessage).issueTypes,
      )
        .then((result) => {
          sendResponse({ ok: true, data: result });
        })
        .catch((error: unknown) => {
          sendResponse({
            ok: false,
            error:
              error instanceof Error ? error.message : BACKGROUND_REPORT_ERROR_MESSAGE,
          });
        });
      return true;
    }
  });
}
