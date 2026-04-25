import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  MANUAL_REPORT_MENU_ID,
  VERIFY_TRANSPARENT_MENU_ID,
  buildManualReportMenuOptions,
  buildTransparentVerificationMenuOptions,
  postFeedbackFromBackground,
} from './background';

function makeFeedbackPayload() {
  return {
    feedback_id: 'feedback-background-1',
    item_id: 'card-1',
    item_hash: null,
    channel_name: 'Test channel',
    model_version: 'extension-runtime',
    policy_version: 'adaptive-threshold-v1',
    action_shown: 'ask-report',
    user_action: 'confirm-report',
    explanation_id: 'exp-test',
    before_score: 0.72,
    after_score: 0.33,
    timestamp: '2026-04-25T10:00:00.000Z',
  };
}

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

  it('posts valid feedback from the background relay', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });

    const result = await postFeedbackFromBackground(
      makeFeedbackPayload(),
      fetchMock as unknown as typeof fetch,
    );

    expect(result).toEqual({ ok: true, status: 200 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/feedback'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('rejects invalid feedback before relaying it', async () => {
    const fetchMock = vi.fn();

    const result = await postFeedbackFromBackground(
      { item_id: '' },
      fetchMock as unknown as typeof fetch,
    );

    expect(result.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('times out hanging background feedback requests', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation(() => new Promise(() => {}));

    const resultPromise = postFeedbackFromBackground(
      makeFeedbackPayload(),
      fetchMock as unknown as typeof fetch,
    );
    await vi.advanceTimersByTimeAsync(6000);
    const result = await resultPromise;

    expect(result.ok).toBe(false);
    if (result.ok) {
      throw new Error('Expected background feedback request to time out.');
    }
    expect(result.error).toContain('timed out');
  });
});
