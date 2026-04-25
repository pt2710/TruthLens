import type {
  ManualReportRequestedOutcome,
  ScoreResult,
} from '@truthlens/shared-schemas';

import {
  feedHistoryAdjustmentScore,
  truthBandFromScore,
  truthScore,
  type TruthBand,
} from './feedScoreTruth';

export type ReportScoreAdjustment = {
  adjustedScore: ScoreResult;
  afterRiskScore: number;
  afterTruthScore: number;
  afterTruthBand: TruthBand;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function roundToOne(value: number): number {
  return Math.round(value * 10) / 10;
}

function roundToFour(value: number): number {
  return Math.round(value * 10000) / 10000;
}

function repeatedReportRedFloor(channelReportCount: number): number {
  const boundedReportCount = Math.max(Math.floor(channelReportCount), 0);
  return roundToOne(clamp(1 - boundedReportCount * 0.14, 0.1, 1.0));
}

function reportedHistoryPathScore(
  requestedOutcome: ManualReportRequestedOutcome,
  channelReportCount: number,
): number {
  const repeatedReportPressure = Math.min(Math.max(channelReportCount, 0), 6) * 0.04;
  const base = requestedOutcome === 'remove' ? 0.72 : 0.22;
  return roundToFour(clamp(base + repeatedReportPressure, 0, 0.92));
}

export function targetTruthScoreAfterReport(
  score: ScoreResult,
  requestedOutcome: ManualReportRequestedOutcome,
  channelReportCount = 0,
): number {
  if (requestedOutcome === 'remove' || score.recommended_action === 'hide') {
    return repeatedReportRedFloor(channelReportCount);
  }

  const currentBand = truthBandFromScore(truthScore(score));
  if (currentBand === 'green' || currentBand === 'yellow') {
    return 4.9;
  }
  if (currentBand === 'orange') {
    return 3.3;
  }
  return repeatedReportRedFloor(channelReportCount);
}

export function adjustScoreForReportedContent(
  score: ScoreResult,
  requestedOutcome: ManualReportRequestedOutcome,
  channelReportCount = 0,
): ReportScoreAdjustment {
  const afterTruthScore = targetTruthScoreAfterReport(
    score,
    requestedOutcome,
    channelReportCount,
  );
  const nextPathScores = {
    ...score.path_scores,
    history: Math.max(
      Number(score.path_scores.history ?? 0),
      reportedHistoryPathScore(requestedOutcome, channelReportCount),
    ),
  };
  const scoreWithHistory = {
    ...score,
    path_scores: nextPathScores,
  };
  const targetFeedRisk = clamp(10 - afterTruthScore, 0, 10);
  const targetRuntimeRisk = clamp(
    (targetFeedRisk - feedHistoryAdjustmentScore(scoreWithHistory)) / 10,
    0,
    1,
  );
  const nextRiskScore = roundToFour(Math.max(targetRuntimeRisk, score.risk_score));
  const nextAction = requestedOutcome === 'remove' || score.recommended_action === 'hide'
    ? 'hide'
    : 'ask-report';
  const adjustedScore: ScoreResult = {
    ...score,
    risk_score: nextRiskScore,
    fused_score: Math.max(score.fused_score, nextRiskScore),
    calibrated_score: Math.max(score.calibrated_score, nextRiskScore),
    path_scores: nextPathScores,
    recommended_action: nextAction,
    reasons:
      score.reasons.length > 0
        ? score.reasons
        : ['Creator report feedback adjusted this feed score.'],
    explanation_id: score.explanation_id ?? 'truthlens-creator-report-feedback',
    explanation_summary:
      score.explanation_summary ??
      'Creator report feedback adjusted this item into a lower trust band.',
  };

  return {
    adjustedScore,
    afterRiskScore: nextRiskScore,
    afterTruthScore: roundToOne(afterTruthScore),
    afterTruthBand: truthBandFromScore(afterTruthScore),
  };
}

export function riskScoreAfterReportFeedback(
  score: ScoreResult | null,
  requestedOutcome: ManualReportRequestedOutcome,
  channelReportCount = 0,
): number | null {
  if (!score) {
    return null;
  }
  return adjustScoreForReportedContent(
    score,
    requestedOutcome,
    channelReportCount,
  ).afterRiskScore;
}
