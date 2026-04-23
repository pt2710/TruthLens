import type { ScoreResult } from '@truthlens/shared-schemas';

import type { FeedbackChannelProfile } from './api';

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
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
