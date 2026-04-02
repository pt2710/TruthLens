import type { ManualReportWorkflowMode, ScoreResult } from '@truthlens/shared-schemas';

export type ReviewPromptDecision = {
  workflowMode: ManualReportWorkflowMode;
  label: string;
  reason: string;
  autoOpen: boolean;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function inferReviewPromptDecision(
  score: ScoreResult,
  musicLikelihood: number,
): ReviewPromptDecision | null {
  const boundedMusicLikelihood = clamp(musicLikelihood, 0, 1);

  if (score.recommended_action === 'ask-report') {
    return {
      workflowMode: 'report',
      label: 'Review report',
      reason: 'TruthLens wants a manual clickbait review for this item.',
      autoOpen: score.confidence >= 0.8 && score.risk_score >= 0.68,
    };
  }

  if (
    boundedMusicLikelihood >= 0.5 &&
    score.risk_score <= 0.32 &&
    score.confidence >= 0.65 &&
    (score.recommended_action === 'none' || score.recommended_action === 'badge')
  ) {
    return {
      workflowMode: 'verify-transparent',
      label: 'Verify transparent',
      reason: 'TruthLens thinks this likely looks like transparent music content.',
      autoOpen: boundedMusicLikelihood >= 0.72 && score.confidence >= 0.8 && score.risk_score <= 0.18,
    };
  }

  return null;
}
