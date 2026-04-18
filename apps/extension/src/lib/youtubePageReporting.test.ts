// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { submitYouTubePageReport } from './youtubePageReporting';

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

describe('submitYouTubePageReport', () => {
  afterEach(() => {
    document.body.innerHTML = '';
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

  it('recovers when a misleading report target navigates to report history before the real dialog opens', async () => {
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
          <div role="menuitem" id="misleading-report-item">Report</div>
          <div role="menuitem" id="real-report-item">Report this video</div>
        </div>
      </ytd-menu-popup-renderer>
    `;

    window.history.replaceState({}, '', '/feed/subscriptions');

    const menuButton = document.querySelector<HTMLButtonElement>('button[aria-label="Action menu"]');
    const menuRoot = document.querySelector<HTMLElement>('#menu-root');
    const misleadingReportItem = document.querySelector<HTMLElement>('#misleading-report-item');
    const realReportItem = document.querySelector<HTMLElement>('#real-report-item');
    if (!menuButton || !menuRoot || !misleadingReportItem || !realReportItem) {
      throw new Error('Failed to build navigation recovery DOM fixture.');
    }

    menuButton.addEventListener('click', () => {
      menuRoot.hidden = false;
    });

    misleadingReportItem.addEventListener('click', () => {
      window.history.pushState({}, '', '/reporthistory');
      menuRoot.hidden = true;
    });

    realReportItem.addEventListener('click', () => {
      installDialog();
    });

    const backSpy = vi.spyOn(window.history, 'back').mockImplementation(() => {
      window.history.pushState({}, '', '/feed/subscriptions');
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

    expect(backSpy).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe('/feed/subscriptions');
    expect(result.status).toBe('reported');
    backSpy.mockRestore();
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
