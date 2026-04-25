import type {
  ManualReportWorkflowMode,
  ManualReviewCollectionScope,
  ScoreResult,
} from '@truthlens/shared-schemas';
import { create } from 'zustand';

import { persistExtensionSessionStats } from '../lib/sessionStats';

export type ManualReportTarget = {
  itemId: string;
  workflowMode: ManualReportWorkflowMode;
  title: string;
  channelName: string;
  channelUrl: string | null;
  linkUrl: string | null;
  thumbnailRef: string | null;
  descriptionSnapshot: string | null;
  transcriptExcerpt: string | null;
  collectionScope: ManualReviewCollectionScope | null;
  channelReportCount: number;
  score: ScoreResult | null;
};

type OverlayState = {
  itemCount: number;
  flaggedCount: number;
  lastScore: ScoreResult | null;
  scoresByItemId: Record<string, ScoreResult>;
  manualReportTarget: ManualReportTarget | null;
  recordScore: (itemId: string, score: ScoreResult) => void;
  openManualReport: (target: ManualReportTarget) => void;
  closeManualReport: () => void;
};

export const useOverlayStore = create<OverlayState>((set) => ({
  itemCount: 0,
  flaggedCount: 0,
  lastScore: null,
  scoresByItemId: {},
  manualReportTarget: null,
  recordScore: (itemId, score) =>
    set((state) => {
      const nextScores = { ...state.scoresByItemId, [itemId]: score };
      const flaggedCount = Object.values(nextScores).filter(
        (entry) => entry.recommended_action !== 'none',
      ).length;
      const nextState = {
        itemCount: Object.keys(nextScores).length,
        flaggedCount,
        lastScore: score,
        scoresByItemId: nextScores,
      };
      void persistExtensionSessionStats({
        itemCount: nextState.itemCount,
        flaggedCount: nextState.flaggedCount,
        lastScore: nextState.lastScore,
        updatedAt: new Date().toISOString(),
      });
      return nextState;
    }),
  openManualReport: (target) => set({ manualReportTarget: target }),
  closeManualReport: () => set({ manualReportTarget: null }),
}));
