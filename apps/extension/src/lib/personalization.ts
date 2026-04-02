import type { ScoreResult } from '@truthlens/shared-schemas';

import type { FeedbackChannelProfile } from './api';

export type PersonalizationBucket = 'boosted' | 'steady' | 'downranked';

export type PersonalizationSnapshot = {
  bucket: PersonalizationBucket;
  displayScore: number;
  rankingScore: number;
  trustScore: number;
  reportRatio: number;
  transparentRatio: number;
  reasons: string[];
};

const ACTION_ADJUSTMENTS: Record<ScoreResult['recommended_action'], number> = {
  none: 1.35,
  badge: 0.15,
  blur: -1.45,
  'ask-report': -2.25,
  hide: -3.2,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function roundToTwo(value: number): number {
  return Math.round(value * 100) / 100;
}

export function describePersonalizationBucket(bucket: PersonalizationBucket): string {
  switch (bucket) {
    case 'boosted':
      return 'boosted';
    case 'downranked':
      return 'downranked';
    default:
      return 'steady';
  }
}

export function shouldShowPersonalizationBadge(
  snapshot: PersonalizationSnapshot,
  score: ScoreResult,
): boolean {
  return (
    score.recommended_action !== 'none' ||
    snapshot.bucket !== 'steady' ||
    Math.abs(snapshot.trustScore - 5.0) >= 2.25
  );
}

export function buildPersonalizationSnapshot(
  score: ScoreResult,
  profile: FeedbackChannelProfile | undefined,
): PersonalizationSnapshot {
  const trustScore = clamp(profile?.trust_score ?? 5.0, 0.0, 10.0);
  const scoredItemCount = Math.max(profile?.scored_item_count ?? 0, 0);
  const reportedItemCount = Math.max(
    profile?.reported_item_count ?? profile?.report_count ?? 0,
    0,
  );
  const transparentCount = Math.max(profile?.transparent_count ?? 0, 0);
  const moderateRequestCount = Math.max(profile?.moderate_request_count ?? 0, 0);
  const removeRequestCount = Math.max(profile?.remove_request_count ?? 0, 0);
  const reportRatio =
    scoredItemCount > 0 ? clamp(reportedItemCount / scoredItemCount, 0.0, 1.0) : 0.0;
  const transparentRatio =
    scoredItemCount > 0 ? clamp(transparentCount / scoredItemCount, 0.0, 1.0) : 0.0;
  const moderationPressure = moderateRequestCount * 0.08 + removeRequestCount * 0.14;
  const feedbackDrift = clamp(
    transparentRatio * 2.0 - reportRatio * 3.1 - moderationPressure * 1.4,
    -3.5,
    3.5,
  );
  const itemTrustBase = (1.0 - score.risk_score) * 10.0;
  const trustOffset = (trustScore - 5.0) * 0.7;
  const riskSpread = (0.5 - score.risk_score) * 7.2;
  const certaintyAdjustment =
    (score.confidence - 0.5) * 2.2 - (score.uncertainty - 0.2) * 0.8;
  const displayScore = clamp(
    roundToTwo(
      itemTrustBase +
        (trustScore - 5.0) * 0.35 +
        transparentRatio * 1.1 -
        reportRatio * 1.2 -
        moderationPressure * 0.45 +
        (score.confidence - score.uncertainty) * 0.9,
    ),
    0.0,
    10.0,
  );
  const rankingScore = clamp(
    roundToTwo(
      5.0 +
        trustOffset +
        feedbackDrift +
        riskSpread +
        certaintyAdjustment +
        ACTION_ADJUSTMENTS[score.recommended_action],
    ),
    0.0,
    10.0,
  );
  const bucket: PersonalizationBucket =
    rankingScore >= 7.25 ? 'boosted' : rankingScore >= 4.5 ? 'steady' : 'downranked';

  const reasons: string[] = [];
  if (trustScore >= 7.0) {
    reasons.push('channel has a strong local TruthLens trust score');
  } else if (trustScore <= 4.0) {
    reasons.push('channel has a weak local TruthLens trust score');
  }
  if (transparentRatio >= 0.25) {
    reasons.push('past transparency confirmations support this channel');
  }
  if (reportRatio >= 0.25) {
    reasons.push('past manual reports lower local confidence for this channel');
  }
  if (score.risk_score <= 0.25) {
    reasons.push('the current item looks relatively consistent on this pass');
  } else if (score.risk_score >= 0.65) {
    reasons.push('the current item carries a high misleading-risk estimate');
  } else {
    reasons.push('the current item remains in a mid-risk review band');
  }

  return {
    bucket,
    displayScore,
    rankingScore,
    trustScore: roundToTwo(trustScore),
    reportRatio: roundToTwo(reportRatio),
    transparentRatio: roundToTwo(transparentRatio),
    reasons,
  };
}
