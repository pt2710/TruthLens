import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  MANUAL_REPORT_MENU_ID,
  VERIFY_TRANSPARENT_MENU_ID,
  buildManualReportMenuOptions,
  submitPageReportInBackground,
  buildTransparentVerificationMenuOptions,
} from './background';

describe('background manual report menu', () => {
  afterEach(() => {
    vi.useRealTimers();
    Reflect.deleteProperty(globalThis, 'chrome');
  });

  it('builds the YouTube context menu configuration for manual reports', () => {
    expect(buildManualReportMenuOptions()).toEqual({
      id: MANUAL_REPORT_MENU_ID,
      title: 'Report video with TruthLens',
      contexts: ['image', 'link'],
      documentUrlPatterns: ['https://www.youtube.com/*'],
    });
  });

  it('builds the YouTube context menu configuration for transparent verification', () => {
    expect(buildTransparentVerificationMenuOptions()).toEqual({
      id: VERIFY_TRANSPARENT_MENU_ID,
      title: 'Verify transparent with TruthLens',
      contexts: ['image', 'link'],
      documentUrlPatterns: ['https://www.youtube.com/*'],
    });
  });

  it('submits the protected YouTube report flow in a background tab and closes it afterwards', async () => {
    const create = vi.fn().mockResolvedValue({ id: 17 });
    const sendMessage = vi.fn().mockResolvedValue({
      ok: true,
      data: {
        status: 'reported',
        reason_label: 'Spam or misleading',
        secondary_reason_label: 'Misleading metadata',
      },
    });
    const remove = vi.fn().mockResolvedValue(undefined);

    Object.assign(globalThis, {
      chrome: {
        tabs: {
          create,
          sendMessage,
          remove,
        },
      },
    });

    vi.useFakeTimers();
    const promise = submitPageReportInBackground(
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

    await vi.advanceTimersByTimeAsync(1200);
    const result = await promise;

    expect(create).toHaveBeenCalledWith({
      url: 'https://www.youtube.com/watch?v=test-video',
      active: false,
    });
    expect(sendMessage).toHaveBeenCalledWith(17, {
      type: 'TRUTHLENS_EXECUTE_PAGE_REPORT',
      target: expect.objectContaining({
        itemId: 'item-1',
        linkUrl: 'https://www.youtube.com/watch?v=test-video',
      }),
      issueTypes: ['title'],
    });
    expect(remove).toHaveBeenCalledWith(17);
    expect(result).toEqual({
      status: 'reported',
      reason_label: 'Spam or misleading',
      secondary_reason_label: 'Misleading metadata',
    });
  });
});
