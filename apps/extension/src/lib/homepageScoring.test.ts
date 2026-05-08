import { describe, expect, it, vi } from 'vitest';

import {
  collectSafePendingEntries,
  HOMEPAGE_STARTUP_RETRY_DELAY_MS,
  shouldScheduleHomepageStartupRetry,
  splitResponsivePendingEntries,
} from './homepageScoring';

describe('homepageScoring', () => {
  it('continues collecting entries when one card extraction throws', () => {
    const onError = vi.fn();
    const result = collectSafePendingEntries(
      ['first', 'broken', 'third'],
      (value) => {
        if (value === 'broken') {
          throw new Error('localStorage blocked');
        }
        return value.toUpperCase();
      },
      onError,
    );

    expect(result).toEqual(['FIRST', 'THIRD']);
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('schedules exactly one startup retry on the homepage when nothing is pending', () => {
    expect(shouldScheduleHomepageStartupRetry('/', 'startup', 0, 0)).toBe(true);
    expect(HOMEPAGE_STARTUP_RETRY_DELAY_MS).toBeGreaterThan(0);
    expect(shouldScheduleHomepageStartupRetry('/', 'homepage-retry', 0, 1)).toBe(false);
    expect(shouldScheduleHomepageStartupRetry('/', 'startup', 2, 0)).toBe(false);
    expect(shouldScheduleHomepageStartupRetry('/watch', 'startup', 0, 0)).toBe(false);
  });

  it('splits a responsive scoring pass from deferred infinite-scroll backlog', () => {
    const { entriesForPass, deferredEntries } = splitResponsivePendingEntries(
      ['card-1', 'card-2', 'card-3', 'card-4'],
      2,
    );

    expect(entriesForPass).toEqual(['card-1', 'card-2']);
    expect(deferredEntries).toEqual(['card-3', 'card-4']);
  });
});
