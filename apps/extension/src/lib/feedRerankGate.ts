export const RERANK_CHUNK_ID_ATTR = 'data-truthlens-rerank-chunk-id';
export const RERANK_CHUNK_SEALED_ATTR = 'data-truthlens-rerank-chunk-sealed';

export function shouldRestoreOriginalOrderingWhenDisabled(
  cards: readonly HTMLElement[],
): boolean {
  return cards.some(
    (card) =>
      card.getAttribute(RERANK_CHUNK_ID_ATTR) !== null ||
      card.getAttribute(RERANK_CHUNK_SEALED_ATTR) !== null,
  );
}

