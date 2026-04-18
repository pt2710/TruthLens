// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';

import { submitYouTubePageReport } from './youtubePageReporting';

function installCardDom(): {
  card: HTMLElement;
  menuButton: HTMLButtonElement;
  reportMenuItem: HTMLElement;
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
    <div id="menu-root">
      <ytd-menu-service-item-renderer hidden>Report</ytd-menu-service-item-renderer>
    </div>
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
