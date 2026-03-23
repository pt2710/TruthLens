import type { ScoreResult } from '@truthlens/shared-schemas';
import { create } from 'zustand';

type OverlayState = {
  itemCount: number;
  flaggedCount: number;
  lastScore: ScoreResult | null;
  scoresByItemId: Record<string, ScoreResult>;
  recordScore: (itemId: string, score: ScoreResult) => void;
};

export const useOverlayStore = create<OverlayState>((set) => ({
  itemCount: 0,
  flaggedCount: 0,
  lastScore: null,
  scoresByItemId: {},
  recordScore: (itemId, score) =>
    set((state) => {
      const nextScores = { ...state.scoresByItemId, [itemId]: score };
      const flaggedCount = Object.values(nextScores).filter(
        (entry) => entry.recommended_action !== 'none',
      ).length;
      return {
        itemCount: Object.keys(nextScores).length,
        flaggedCount,
        lastScore: score,
        scoresByItemId: nextScores,
      };
    }),
}));
