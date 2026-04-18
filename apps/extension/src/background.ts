import { buildTruthLensApiUrl } from './lib/runtimeConfig';

export const MANUAL_REPORT_MENU_ID = 'truthlens-manual-report';
export const VERIFY_TRANSPARENT_MENU_ID = 'truthlens-verify-transparent';

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

  });
}
