import type { ScoreResult } from '@truthlens/shared-schemas';
import { beforeEach, describe, expect, it } from 'vitest';

import { useOverlayStore } from './store';

function score(action: ScoreResult['recommended_action']): ScoreResult {
  return {
    risk_score: 0.6,
    confidence: 0.8,
    uncertainty: 0.2,
    recommended_action: action,
    reasons: action === 'none' ? [] : ['reason'],
    explanation_id: action === 'none' ? null : 'exp-test',
    explanation_summary: action === 'none' ? null : 'reason',
    evidence: [],
  };
}

describe('overlay store', () => {
  beforeEach(() => {
    useOverlayStore.setState({
      itemCount: 0,
      flaggedCount: 0,
      lastScore: null,
      scoresByItemId: {},
      manualReportTarget: null,
      recordScore: useOverlayStore.getState().recordScore,
      openManualReport: useOverlayStore.getState().openManualReport,
      closeManualReport: useOverlayStore.getState().closeManualReport,
    });
  });

  it('tracks unique items instead of incrementing duplicates', () => {
    const { recordScore } = useOverlayStore.getState();

    recordScore('item-1', score('badge'));
    recordScore('item-1', score('none'));
    recordScore('item-2', score('blur'));

    const state = useOverlayStore.getState();
    expect(state.itemCount).toBe(2);
    expect(state.flaggedCount).toBe(1);
    expect(state.lastScore?.recommended_action).toBe('blur');
  });

  it('opens and closes the manual report target', () => {
    const { openManualReport, closeManualReport } = useOverlayStore.getState();

    openManualReport({
      itemId: 'item-3',
      workflowMode: 'report',
      title: 'Secret lab leak exposed in new footage',
      channelName: 'Signal Watch Europe',
      channelUrl: 'https://www.youtube.com/@signalwatcheurope',
      linkUrl: 'https://www.youtube.com/watch?v=item-3',
      thumbnailRef: 'https://example.com/thumb-3.jpg',
      descriptionSnapshot: 'Metadata snippet referencing the claimed leak.',
      transcriptExcerpt: 'Short transcript excerpt with vague claims.',
      score: score('ask-report'),
    });

    expect(useOverlayStore.getState().manualReportTarget?.itemId).toBe('item-3');

    closeManualReport();

    expect(useOverlayStore.getState().manualReportTarget).toBeNull();
  });
});
