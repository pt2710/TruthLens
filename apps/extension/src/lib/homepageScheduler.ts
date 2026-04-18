import type { HomepageScoreTrigger } from './homepageScoring';

type ScoreRunner = (trigger: HomepageScoreTrigger) => Promise<void> | void;
type QueueListener = (trigger: HomepageScoreTrigger) => void;

export function createHomepageScoreScheduler(
  run: ScoreRunner,
  onQueue?: QueueListener,
) {
  let inFlight = false;
  let pendingTrigger: HomepageScoreTrigger | null = null;

  async function flush(trigger: HomepageScoreTrigger): Promise<void> {
    inFlight = true;
    let currentTrigger: HomepageScoreTrigger | null = trigger;

    try {
      while (currentTrigger) {
        await run(currentTrigger);
        currentTrigger = pendingTrigger;
        pendingTrigger = null;
      }
    } finally {
      inFlight = false;
      if (pendingTrigger) {
        const nextTrigger = pendingTrigger;
        pendingTrigger = null;
        void flush(nextTrigger);
      }
    }
  }

  return {
    request(trigger: HomepageScoreTrigger): void {
      if (inFlight) {
        pendingTrigger = trigger;
        onQueue?.(trigger);
        return;
      }

      void flush(trigger);
    },
    isInFlight(): boolean {
      return inFlight;
    },
    getPendingTrigger(): HomepageScoreTrigger | null {
      return pendingTrigger;
    },
  };
}
