import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  MANUAL_REPORT_MENU_ID,
  VERIFY_TRANSPARENT_MENU_ID,
  buildManualReportMenuOptions,
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
});
