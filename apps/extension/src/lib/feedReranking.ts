import type { ScoreResult } from '@truthlens/shared-schemas';

import type { FeedbackChannelProfile } from './api';
import {
  feedHistoryAdjustmentScore,
  feedRiskScore,
  type TruthBand,
  truthBandFromScore,
  truthScore,
} from './feedScoreTruth';
import type { PersonalizationSnapshot } from './personalization';
import type { ReviewPromptDecision } from './reviewPrompts';

export type FeedPresentationSnapshot = {
  truthScore: number;
  truthBand: TruthBand;
  feedRiskScore: number;
  runtimeRiskScore: number;
  historyAdjustmentScore: number;
  rerankPriority: number;
  rerankLocked: boolean;
};

export type FeedRerankCandidate<TCard = string> = {
  card: TCard;
  originalIndex: number;
  rerankPriority: number;
  rerankLocked: boolean;
  truthBand: TruthBand;
};

const SEVERE_NEGATIVE_BIASES = new Set([
  'channel-lock-in-risk',
  'sensational-overweighting',
]);

const CREATIVE_CLASSES = new Set(['music', 'art', 'gaming']);

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function roundToOne(value: number): number {
  return Math.round(value * 10) / 10;
}

function strongTransparentHistory(profile: FeedbackChannelProfile | undefined): boolean {
  const transparentCount = Number(profile?.transparent_count ?? 0);
  const reportedItemCount = Number(profile?.reported_item_count ?? profile?.report_count ?? 0);
  const trustScore = Number(profile?.trust_score ?? 5);
  return transparentCount >= 2 || (trustScore >= 7.5 && reportedItemCount <= Math.max(transparentCount, 1));
}

function reviewPromptTruthScoreCap(
  score: ScoreResult,
  reviewPrompt: ReviewPromptDecision | null,
): number {
  if (reviewPrompt?.workflowMode !== 'report') {
    return 10;
  }
  if (score.recommended_action === 'ask-report' || score.recommended_action === 'hide') {
    return 4.9;
  }
  return 6.6;
}

export function buildFeedPresentationSnapshot(
  score: ScoreResult,
  personalization: PersonalizationSnapshot,
  profile: FeedbackChannelProfile | undefined,
  reviewPrompt: ReviewPromptDecision | null,
  rerankLocked: boolean,
): FeedPresentationSnapshot {
  const scoreCap = reviewPromptTruthScoreCap(score, reviewPrompt);
  const nextTruthScore = Math.min(truthScore(score), scoreCap);
  const nextTruthBand = truthBandFromScore(nextTruthScore);
  const nextFeedRiskScore = Math.max(feedRiskScore(score), 10 - nextTruthScore);
  const historyAdjustment = feedHistoryAdjustmentScore(score);
  const runtimeRiskScore = Number((score.risk_score * 10).toFixed(1));
  const negativeBiases = new Set(score.bias_profile.negative_biases);
  const reportedItemCount = Number(profile?.reported_item_count ?? profile?.report_count ?? 0);
  const hasSevereNegativeBias = Array.from(SEVERE_NEGATIVE_BIASES).some((bias) => negativeBiases.has(bias));
  const creativeProtected =
    CREATIVE_CLASSES.has(score.content_class) &&
    score.content_class_confidence >= 0.7 &&
    !hasSevereNegativeBias &&
    reportedItemCount < 2;
  const satireProtected =
    score.content_class === 'satire' &&
    !hasSevereNegativeBias &&
    score.recommended_action !== 'ask-report' &&
    score.recommended_action !== 'hide' &&
    reportedItemCount < 2 &&
    negativeBiases.has('genre-confusion');

  let rerankPriority = 0.7 * nextTruthScore + 0.3 * personalization.rankingScore;

  if (score.recommended_action === 'hide') {
    rerankPriority -= 1.6;
  } else if (score.recommended_action === 'ask-report') {
    rerankPriority -= 1.2;
  } else if (score.recommended_action === 'blur') {
    rerankPriority -= 0.8;
  } else if (score.recommended_action === 'badge') {
    rerankPriority -= 0.25;
  }

  if ((score.path_scores.history ?? 0) >= 0.55 || reportedItemCount >= 2) {
    rerankPriority -= 0.6;
  }

  if (hasSevereNegativeBias) {
    rerankPriority -= 0.4;
  }

  if (reviewPrompt?.workflowMode === 'verify-transparent') {
    rerankPriority += 0.8;
  }

  if (creativeProtected) {
    rerankPriority += 0.5;
  }

  if (
    strongTransparentHistory(profile) &&
    (score.recommended_action === 'none' || score.recommended_action === 'badge')
  ) {
    rerankPriority += 0.3;
  }

  if (creativeProtected || satireProtected) {
    rerankPriority = Math.max(rerankPriority, 5.0);
  }

  return {
    truthScore: roundToOne(nextTruthScore),
    truthBand: nextTruthBand,
    feedRiskScore: roundToOne(nextFeedRiskScore),
    runtimeRiskScore: roundToOne(runtimeRiskScore),
    historyAdjustmentScore: roundToOne(historyAdjustment),
    rerankPriority: roundToOne(clamp(rerankPriority, 0, 10)),
    rerankLocked,
  };
}

function maxShiftForTruthBand(truthBand: TruthBand): number {
  return truthBand === 'red' || truthBand === 'green' ? 6 : 3;
}

export function planStableRerankOrder<TCard>(
  candidates: FeedRerankCandidate<TCard>[],
): TCard[] {
  if (candidates.length <= 1) {
    return candidates.map((candidate) => candidate.card);
  }

  const movable = candidates.filter((candidate) => !candidate.rerankLocked);
  if (movable.length <= 1) {
    return candidates.map((candidate) => candidate.card);
  }

  const desiredOrder = [...movable].sort((left, right) => {
    if (right.rerankPriority !== left.rerankPriority) {
      return right.rerankPriority - left.rerankPriority;
    }
    return left.originalIndex - right.originalIndex;
  });
  const desiredRankByCard = new Map<TCard, number>(
    desiredOrder.map((candidate, index) => [candidate.card, index]),
  );
  const originalRankByCard = new Map<TCard, number>(
    movable.map((candidate, index) => [candidate.card, index]),
  );
  const targetRankByCard = new Map<TCard, number>();

  movable.forEach((candidate) => {
    const desiredRank = desiredRankByCard.get(candidate.card) ?? 0;
    const originalRank = originalRankByCard.get(candidate.card) ?? 0;
    const maxShift = maxShiftForTruthBand(candidate.truthBand);
    targetRankByCard.set(
      candidate.card,
      clamp(desiredRank, originalRank - maxShift, originalRank + maxShift),
    );
  });

  const reorderedMovable = [...movable].sort((left, right) => {
    const leftTarget = targetRankByCard.get(left.card) ?? 0;
    const rightTarget = targetRankByCard.get(right.card) ?? 0;
    if (leftTarget !== rightTarget) {
      return leftTarget - rightTarget;
    }
    if (right.rerankPriority !== left.rerankPriority) {
      return right.rerankPriority - left.rerankPriority;
    }
    return left.originalIndex - right.originalIndex;
  });

  const movableQueue = [...reorderedMovable];
  return candidates.map((candidate) => {
    if (candidate.rerankLocked) {
      return candidate.card;
    }
    return movableQueue.shift()!.card;
  });
}
