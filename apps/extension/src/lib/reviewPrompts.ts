import type { ManualReportWorkflowMode, ScoreResult } from '@truthlens/shared-schemas';

export type ReviewPromptDecision = {
  workflowMode: ManualReportWorkflowMode;
  label: string;
  reason: string;
};

const TRANSPARENT_REVIEW_CLASSES = new Set(['music', 'art', 'gaming']);
const AMBIGUOUS_REVIEW_CLASSES = new Set(['satire']);
const SEVERE_NEGATIVE_BIASES = new Set([
  'sensational-overweighting',
  'channel-lock-in-risk',
]);

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function inferReviewPromptDecision(
  score: ScoreResult,
  musicLikelihood: number,
): ReviewPromptDecision {
  const boundedMusicLikelihood = clamp(musicLikelihood, 0, 1);
  const resolvedClass = score.content_class;
  const negativeBiases = new Set(score.bias_profile.negative_biases);

  if (score.recommended_action === 'ask-report' || score.recommended_action === 'hide') {
    return {
      workflowMode: 'report',
      label: 'Review report',
      reason: 'TruthLens wants a manual clickbait review for this item.',
    };
  }

  if (
    AMBIGUOUS_REVIEW_CLASSES.has(resolvedClass) &&
    (score.recommended_action === 'none' ||
      score.recommended_action === 'badge' ||
      score.recommended_action === 'blur') &&
    (negativeBiases.has('genre-confusion') ||
      negativeBiases.has('uncertainty-miscalibration') ||
      score.uncertainty >= 0.22)
  ) {
    return {
      workflowMode: 'report',
      label: 'Review report',
      reason: 'TruthLens sees satire-like or ambiguous packaging that still needs human confirmation.',
    };
  }

  if (
    ((TRANSPARENT_REVIEW_CLASSES.has(resolvedClass) &&
      score.content_class_confidence >= 0.7) ||
      (resolvedClass === 'unknown' && boundedMusicLikelihood >= 0.5)) &&
    score.risk_score <= 0.32 &&
    score.confidence >= 0.65 &&
    (score.recommended_action === 'none' || score.recommended_action === 'badge') &&
    !Array.from(SEVERE_NEGATIVE_BIASES).some((bias) => negativeBiases.has(bias))
  ) {
    const classLabel = TRANSPARENT_REVIEW_CLASSES.has(resolvedClass)
      ? resolvedClass
      : 'music';
    return {
      workflowMode: 'verify-transparent',
      label: 'Verify transparent',
      reason: `TruthLens thinks this likely looks like transparent ${classLabel} content.`,
    };
  }

  if (
    score.risk_score >= 0.42 ||
    score.recommended_action === 'blur' ||
    Array.from(SEVERE_NEGATIVE_BIASES).some((bias) => negativeBiases.has(bias))
  ) {
    return {
      workflowMode: 'report',
      label: 'Review report',
      reason: 'TruthLens wants a human report decision for this feed item.',
    };
  }

  return {
    workflowMode: 'verify-transparent',
    label: 'Verify transparent',
    reason: 'TruthLens thinks this likely looks transparent enough to verify.',
  };
}
