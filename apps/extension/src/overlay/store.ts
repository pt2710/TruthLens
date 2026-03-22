import type { ScoreResult } from '@truthlens/shared-schemas';
import { create } from 'zustand';

type OverlayState = {
  itemCount: number;
  flaggedCount: number;
  lastScore: ScoreResult | null;
  recordScore: (score: ScoreResult) => void;
};

export const useOverlayStore = create<OverlayState>((set) => ({
  itemCount: 0,
  flaggedCount: 0,
  lastScore: null,
  recordScore: (score) =>
    set((state) => ({
      itemCount: state.itemCount + 1,
      flaggedCount: state.flaggedCount + (score.recommended_action === 'none' ? 0 : 1),
      lastScore: score,
    })),
}));
