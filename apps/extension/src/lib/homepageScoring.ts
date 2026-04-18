export type HomepageScoreTrigger = 'startup' | 'mutation' | 'homepage-retry';

export const HOMEPAGE_STARTUP_RETRY_DELAY_MS = 650;

export function collectSafePendingEntries<TItem, TEntry>(
  items: readonly TItem[],
  buildEntry: (item: TItem, index: number) => TEntry | null,
  onError?: (error: unknown, item: TItem, index: number) => void,
): TEntry[] {
  const entries: TEntry[] = [];

  items.forEach((item, index) => {
    try {
      const entry = buildEntry(item, index);
      if (entry !== null) {
        entries.push(entry);
      }
    } catch (error) {
      onError?.(error, item, index);
    }
  });

  return entries;
}

export function shouldScheduleHomepageStartupRetry(
  pathname: string,
  trigger: HomepageScoreTrigger,
  pendingCount: number,
  retryCount: number,
): boolean {
  return pathname === '/' && trigger === 'startup' && pendingCount === 0 && retryCount === 0;
}
