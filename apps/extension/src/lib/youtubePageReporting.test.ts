// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  submitYouTubePageReport,
  submitYouTubePageReportInDocument,
} from './youtubePageReporting';

function installCardDom(): {
  card: HTMLElement;
  menuButton: HTMLButtonElement;
  reportMenuItem: HTMLElement;
} {
  document.body.innerHTML = `
    <div role="menu">
      <a href="https://www.youtube.com/reporthistory" role="menuitem">Report history</a>
    </div>
    <ytd-rich-item-renderer>
      <a id="thumbnail" href="https://www.youtube.com/watch?v=test-video">
        <img src="https://img.youtube.com/vi/test-video/default.jpg" />
      </a>
      <a id="video-title">Test headline</a>
      <ytd-channel-name>Signal Watch</ytd-channel-name>
      <ytd-menu-renderer>
        <button aria-label="Action menu">More</button>
      </ytd-menu-renderer>
    </ytd-rich-item-renderer>
    <ytd-menu-popup-renderer id="menu-root">
      <ytd-menu-service-item-renderer hidden>Report</ytd-menu-service-item-renderer>
    </ytd-menu-popup-renderer>
  `;

  const card = document.querySelector<HTMLElement>('ytd-rich-item-renderer');
  const menuButton = document.querySelector<HTMLButtonElement>('button[aria-label="Action menu"]');
  const reportMenuItem = document.querySelector<HTMLElement>('ytd-menu-service-item-renderer');

  if (!card || !menuButton || !reportMenuItem) {
    throw new Error('Failed to build YouTube report DOM fixture.');
  }

  menuButton.addEventListener('click', () => {
    reportMenuItem.hidden = false;
  });

  return { card, menuButton, reportMenuItem };
}

function installDialog(primaryReasonLabel = 'Spam or misleading'): HTMLElement {
  const dialog = document.createElement('tp-yt-paper-dialog');
  const primaryReason = document.createElement('tp-yt-paper-radio-button');
  primaryReason.textContent = primaryReasonLabel;
  const submitButton = document.createElement('button');
  submitButton.textContent = 'Submit';
  submitButton.addEventListener('click', () => {
    dialog.remove();
  });
  dialog.append(primaryReason, submitButton);
  document.body.appendChild(dialog);
  return dialog;
}

function installCompetingMenuDom(): {
  menuButton: HTMLButtonElement;
  reportMenuItem: HTMLAnchorElement;
  reportHistoryMenuItem: HTMLAnchorElement;
} {
  document.body.innerHTML = `
    <ytd-rich-item-renderer>
      <a id="thumbnail" href="https://www.youtube.com/watch?v=test-video">
        <img src="https://img.youtube.com/vi/test-video/default.jpg" />
      </a>
      <a id="video-title">Test headline</a>
      <ytd-channel-name>Signal Watch</ytd-channel-name>
      <ytd-menu-renderer>
        <button aria-label="Action menu">More</button>
      </ytd-menu-renderer>
    </ytd-rich-item-renderer>
    <ytd-menu-popup-renderer id="menu-root" hidden>
      <div role="menu">
        <a href="https://www.youtube.com/reporthistory" role="menuitem" id="report-history-item">Report history</a>
        <a href="#report" role="menuitem" id="report-item">Report</a>
      </div>
    </ytd-menu-popup-renderer>
  `;

  const menuButton = document.querySelector<HTMLButtonElement>('button[aria-label="Action menu"]');
  const menuRoot = document.querySelector<HTMLElement>('#menu-root');
  const reportMenuItem = document.querySelector<HTMLAnchorElement>('#report-item');
  const reportHistoryMenuItem = document.querySelector<HTMLAnchorElement>('#report-history-item');

  if (!menuButton || !menuRoot || !reportMenuItem || !reportHistoryMenuItem) {
    throw new Error('Failed to build competing report menu DOM fixture.');
  }

  menuButton.addEventListener('click', () => {
    menuRoot.hidden = false;
  });

  return { menuButton, reportMenuItem, reportHistoryMenuItem };
}

function installWatchPageDom(): {
  menuButton: HTMLButtonElement;
  reportMenuItem: HTMLElement;
} {
  document.body.innerHTML = `
    <ytd-watch-flexy>
      <div id="above-the-fold">
        <ytd-watch-metadata>
          <ytd-menu-renderer>
            <button aria-label="More actions">More actions</button>
          </ytd-menu-renderer>
        </ytd-watch-metadata>
      </div>
    </ytd-watch-flexy>
    <ytd-menu-popup-renderer id="menu-root" hidden>
      <div role="menu">
        <ytd-menu-service-item-renderer id="watch-report-item">Report</ytd-menu-service-item-renderer>
      </div>
    </ytd-menu-popup-renderer>
  `;

  const menuButton = document.querySelector<HTMLButtonElement>('button[aria-label="More actions"]');
  const menuRoot = document.querySelector<HTMLElement>('#menu-root');
  const reportMenuItem = document.querySelector<HTMLElement>('#watch-report-item');
  if (!menuButton || !menuRoot || !reportMenuItem) {
    throw new Error('Failed to build watch page DOM fixture.');
  }

  menuButton.addEventListener('click', () => {
    menuRoot.hidden = false;
  });

  return { menuButton, reportMenuItem };
}

function installConfusingWatchPageDom(): {
  unrelatedButton: HTMLButtonElement;
  menuButton: HTMLButtonElement;
  reportMenuItem: HTMLElement;
} {
  document.body.innerHTML = `
    <ytd-watch-flexy>
      <div id="above-the-fold">
        <button aria-label="More">Unrelated action</button>
        <ytd-watch-metadata>
          <div id="actions">
            <ytd-menu-renderer>
              <button aria-label="More actions">More actions</button>
            </ytd-menu-renderer>
          </div>
        </ytd-watch-metadata>
      </div>
    </ytd-watch-flexy>
    <ytd-menu-popup-renderer id="menu-root" hidden>
      <div role="menu">
        <ytd-menu-service-item-renderer id="watch-report-item">Report</ytd-menu-service-item-renderer>
      </div>
    </ytd-menu-popup-renderer>
  `;

  const unrelatedButton = document.querySelector<HTMLButtonElement>('button[aria-label="More"]');
  const menuButton = document.querySelector<HTMLButtonElement>('button[aria-label="More actions"]');
  const menuRoot = document.querySelector<HTMLElement>('#menu-root');
  const reportMenuItem = document.querySelector<HTMLElement>('#watch-report-item');
  if (!unrelatedButton || !menuButton || !menuRoot || !reportMenuItem) {
    throw new Error('Failed to build confusing watch page DOM fixture.');
  }

  menuButton.addEventListener('click', () => {
    menuRoot.hidden = false;
  });

  return { unrelatedButton, menuButton, reportMenuItem };
}

describe('submitYouTubePageReport', () => {
  afterEach(() => {
    document.body.innerHTML = '';
    Reflect.deleteProperty(globalThis, 'chrome');
  });

  it('submits the report when the dialog appears after a retry click on the same menu item', async () => {
    const { reportMenuItem } = installCardDom();
    let reportClickCount = 0;
    reportMenuItem.addEventListener('click', () => {
      reportClickCount += 1;
      if (reportClickCount === 2) {
        installDialog();
      }
    });

    const result = await submitYouTubePageReport(
      {
        itemId: 'item-1',
        workflowMode: 'report',
        title: 'Test headline',
        channelName: 'Signal Watch',
        channelUrl: 'https://www.youtube.com/@signalwatch',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
        thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        collectionScope: null,
        score: null,
      },
      ['title'],
    );

    expect(reportClickCount).toBe(2);
    expect(result).toEqual({
      status: 'reported',
      reason_label: 'Spam or misleading',
      secondary_reason_label: null,
    });
  });

  it('ignores unrelated visible report links outside the active YouTube card menu', async () => {
    const { reportMenuItem } = installCardDom();
    const reportHistoryLink = document.querySelector<HTMLAnchorElement>('a[href*="reporthistory"]');
    let reportHistoryClicks = 0;
    reportHistoryLink?.addEventListener('click', (event) => {
      reportHistoryClicks += 1;
      event.preventDefault();
    });

    reportMenuItem.addEventListener('click', () => {
      installDialog();
    });

    const result = await submitYouTubePageReport(
      {
        itemId: 'item-1',
        workflowMode: 'report',
        title: 'Test headline',
        channelName: 'Signal Watch',
        channelUrl: 'https://www.youtube.com/@signalwatch',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
        thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        collectionScope: null,
        score: null,
      },
      ['title'],
    );

    expect(reportHistoryClicks).toBe(0);
    expect(result.status).toBe('reported');
  });

  it('submits the report from a watch page surface in the current document', async () => {
    const { reportMenuItem } = installWatchPageDom();
    reportMenuItem.addEventListener('click', () => {
      installDialog();
    });

    const result = await submitYouTubePageReportInDocument(
      {
        itemId: 'item-1',
        workflowMode: 'report',
        title: 'Test headline',
        channelName: 'Signal Watch',
        channelUrl: 'https://www.youtube.com/@signalwatch',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
        thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        collectionScope: null,
        score: null,
      },
      ['title'],
    );

    expect(result.status).toBe('reported');
  });

  it('uses the in-document flow even when chrome.runtime.sendMessage is available', async () => {
    const { reportMenuItem } = installCardDom();
    const sendMessage = vi.fn();
    Object.assign(globalThis, {
      chrome: {
        runtime: {
          sendMessage,
        },
      },
    });

    reportMenuItem.addEventListener('click', () => {
      installDialog();
    });

    const result = await submitYouTubePageReport(
      {
        itemId: 'item-1',
        workflowMode: 'report',
        title: 'Test headline',
        channelName: 'Signal Watch',
        channelUrl: 'https://www.youtube.com/@signalwatch',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
        thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        collectionScope: null,
        score: null,
      },
      ['title'],
    );

    expect(sendMessage).not.toHaveBeenCalled();
    expect(result.status).toBe('reported');
  });

  it('prefers the watch action-bar menu button over broader watch-page buttons when opening the report menu', async () => {
    const { unrelatedButton, reportMenuItem } = installConfusingWatchPageDom();
    let unrelatedClicks = 0;
    unrelatedButton.addEventListener('click', () => {
      unrelatedClicks += 1;
    });
    reportMenuItem.addEventListener('click', () => {
      installDialog();
    });

    const result = await submitYouTubePageReportInDocument(
      {
        itemId: 'item-1',
        workflowMode: 'report',
        title: 'Test headline',
        channelName: 'Signal Watch',
        channelUrl: 'https://www.youtube.com/@signalwatch',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
        thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        collectionScope: null,
        score: null,
      },
      ['title'],
    );

    expect(unrelatedClicks).toBe(0);
    expect(result.status).toBe('reported');
  });

  it('ignores report history menu items inside the visible popup and clicks the real report entry', async () => {
    const { reportMenuItem, reportHistoryMenuItem } = installCompetingMenuDom();
    let reportHistoryClicks = 0;
    reportHistoryMenuItem.addEventListener('click', (event) => {
      reportHistoryClicks += 1;
      event.preventDefault();
    });

    reportMenuItem.addEventListener('click', (event) => {
      event.preventDefault();
      installDialog();
    });

    const result = await submitYouTubePageReport(
      {
        itemId: 'item-1',
        workflowMode: 'report',
        title: 'Test headline',
        channelName: 'Signal Watch',
        channelUrl: 'https://www.youtube.com/@signalwatch',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
        thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        collectionScope: null,
        score: null,
      },
      ['title'],
    );

    expect(reportHistoryClicks).toBe(0);
    expect(result.status).toBe('reported');
  });

  it('prioritizes the newly opened card menu over pre-existing visible report menus elsewhere on the page', async () => {
    document.body.innerHTML = `
      <div role="menu">
        <div role="menuitem" id="global-report-item">Report</div>
      </div>
      <ytd-rich-item-renderer>
        <a id="thumbnail" href="https://www.youtube.com/watch?v=test-video">
          <img src="https://img.youtube.com/vi/test-video/default.jpg" />
        </a>
        <a id="video-title">Test headline</a>
        <ytd-channel-name>Signal Watch</ytd-channel-name>
        <ytd-menu-renderer>
          <button aria-label="Action menu">More</button>
        </ytd-menu-renderer>
      </ytd-rich-item-renderer>
      <ytd-menu-popup-renderer id="menu-root" hidden>
        <div role="menu">
          <ytd-menu-service-item-renderer id="real-report-item">Report</ytd-menu-service-item-renderer>
        </div>
      </ytd-menu-popup-renderer>
    `;

    const menuButton = document.querySelector<HTMLButtonElement>('button[aria-label="Action menu"]');
    const menuRoot = document.querySelector<HTMLElement>('#menu-root');
    const globalReportItem = document.querySelector<HTMLElement>('#global-report-item');
    const realReportItem = document.querySelector<HTMLElement>('#real-report-item');
    if (!menuButton || !menuRoot || !globalReportItem || !realReportItem) {
      throw new Error('Failed to build menu prioritization DOM fixture.');
    }

    menuButton.addEventListener('click', () => {
      menuRoot.hidden = false;
    });

    let globalReportClicks = 0;
    globalReportItem.addEventListener('click', () => {
      globalReportClicks += 1;
    });

    realReportItem.addEventListener('click', () => {
      installDialog();
    });

    const result = await submitYouTubePageReport(
      {
        itemId: 'item-1',
        workflowMode: 'report',
        title: 'Test headline',
        channelName: 'Signal Watch',
        channelUrl: 'https://www.youtube.com/@signalwatch',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
        thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
        descriptionSnapshot: null,
        transcriptExcerpt: null,
        collectionScope: null,
        score: null,
      },
      ['title'],
    );

    expect(globalReportClicks).toBe(0);
    expect(result.status).toBe('reported');
  });

  it(
    'surfaces a specific dialog error when YouTube never opens the report dialog',
    async () => {
      const { reportMenuItem } = installCardDom();
      reportMenuItem.addEventListener('click', () => {
        // Keep the menu item visible, but never mount a dialog.
      });

      await expect(
        submitYouTubePageReport(
          {
            itemId: 'item-1',
            workflowMode: 'report',
            title: 'Test headline',
            channelName: 'Signal Watch',
            channelUrl: 'https://www.youtube.com/@signalwatch',
            linkUrl: 'https://www.youtube.com/watch?v=test-video',
            thumbnailRef: 'https://img.youtube.com/vi/test-video/default.jpg',
            descriptionSnapshot: null,
            transcriptExcerpt: null,
            collectionScope: null,
            score: null,
          },
          ['title'],
        ),
      ).rejects.toThrow(
        'TruthLens found YouTube’s "Report" menu entry, but YouTube did not open the report dialog in time.',
      );
    },
    9000,
  );
});
