import type { ScoreResult } from '@truthlens/shared-schemas';

import type { FeedbackChannelProfile } from './api';

const NEUTRAL_HISTORY_PATH_SCORE = 0.08 + 0.18 * 0.38 + 0.12 * 0.24;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function historyPathScore(score: ScoreResult): number | null {
  const value = Number(score.path_scores?.history);
  if (!Number.isFinite(value)) {
    return null;
  }
  return clamp(value, 0, 1);
}

export function priorFlagsFromProfile(profile: FeedbackChannelProfile | undefined): number {
  return Math.max(Number(profile?.reported_item_count ?? profile?.report_count ?? 0), 0);
}

export function buildChannelHistoryFeatures(
  profile: FeedbackChannelProfile | undefined,
  taxonomyHints: Record<string, number>,
): Record<string, number> {
  if (!profile) {
    return taxonomyHints;
  }
  const trustScore = clamp(Number(profile.trust_score ?? 5), 0, 10);
  const reportedItemCount = priorFlagsFromProfile(profile);
  const scoredItemCount = Math.max(Number(profile.scored_item_count ?? 0), 0);
  return {
    ...taxonomyHints,
    channel_risk_mean: Number(clamp(1 - trustScore / 10, 0, 1).toFixed(4)),
    repeat_template_rate: Number((reportedItemCount / Math.max(scoredItemCount, 1)).toFixed(4)),
    trust_score: Number(trustScore.toFixed(2)),
    reported_item_count: Number(reportedItemCount.toFixed(0)),
    scored_item_count: Number(scoredItemCount.toFixed(0)),
  };
}

export function rawRuntimeRiskScore(score: ScoreResult): number {
  return Number(clamp(score.risk_score * 10, 0, 10).toFixed(1));
}

export function feedHistoryAdjustmentScore(score: ScoreResult): number {
  const historyScore = historyPathScore(score);
  if (historyScore === null) {
    return 0;
  }
  return Number(
    clamp((historyScore - NEUTRAL_HISTORY_PATH_SCORE) * 10, 0, 10).toFixed(1),
  );
}

export function feedDisplayRiskScore(score: ScoreResult): number {
  return Number(
    clamp(
      rawRuntimeRiskScore(score) + feedHistoryAdjustmentScore(score),
      0,
      10,
    ).toFixed(1),
  );
}

export function getRuntimeRiskTone(score: ScoreResult): 'high' | 'medium' | 'low' {
  const runtimeRisk = rawRuntimeRiskScore(score);
  if (score.recommended_action === 'hide' || runtimeRisk >= 7.5) {
    return 'low';
  }
  if (
    score.recommended_action === 'blur' ||
    score.recommended_action === 'ask-report' ||
    runtimeRisk >= 4.5
  ) {
    return 'medium';
  }
  return 'high';
}

export function getFeedRiskTone(score: ScoreResult): 'high' | 'medium' | 'low' {
  const feedRisk = feedDisplayRiskScore(score);
  if (score.recommended_action === 'hide' || feedRisk >= 7.5) {
    return 'low';
  }
  if (
    score.recommended_action === 'blur' ||
    score.recommended_action === 'ask-report' ||
    feedRisk >= 4.5
  ) {
    return 'medium';
  }
  return 'high';
}
