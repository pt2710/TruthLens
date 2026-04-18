import { describe, expect, it } from 'vitest';

import { createHomepageScoreScheduler } from './homepageScheduler';
import type { HomepageScoreTrigger } from './homepageScoring';

function createDeferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

async function flushMicrotasks(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe('createHomepageScoreScheduler', () => {
  it('does not start overlapping runs and replays a queued rerun afterwards', async () => {
    const calls: HomepageScoreTrigger[] = [];
    const queued: HomepageScoreTrigger[] = [];
    const firstRun = createDeferred();
    const secondRun = createDeferred();
    let invocation = 0;

    const scheduler = createHomepageScoreScheduler(async (trigger) => {
      calls.push(trigger);
      invocation += 1;
      if (invocation === 1) {
        await firstRun.promise;
        return;
      }
      await secondRun.promise;
    }, (trigger) => {
      queued.push(trigger);
    });

    scheduler.request('startup');
    scheduler.request('mutation');
    scheduler.request('mutation');
    await flushMicrotasks();

    expect(calls).toEqual(['startup']);
    expect(queued).toEqual(['mutation', 'mutation']);
    expect(scheduler.isInFlight()).toBe(true);
    expect(scheduler.getPendingTrigger()).toBe('mutation');

    firstRun.resolve();
    await flushMicrotasks();

    expect(calls).toEqual(['startup', 'mutation']);
    expect(scheduler.isInFlight()).toBe(true);
    expect(scheduler.getPendingTrigger()).toBeNull();

    secondRun.resolve();
    await flushMicrotasks();

    expect(scheduler.isInFlight()).toBe(false);
  });
});
