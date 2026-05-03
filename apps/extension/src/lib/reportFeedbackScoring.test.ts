import { describe, expect, it } from 'vitest';
import type { ScoreResult } from '@truthlens/shared-schemas';

import {
  adjustScoreForReportedContent,
  targetTruthScoreAfterReport,
} from './reportFeedbackScoring';
import { getTruthBand, truthScore } from './feedScoreTruth';

function makeScore(overrides: Partial<ScoreResult> = {}): ScoreResult {
  return {
    risk_score: 0.2,
    fused_score: 0.2,
    calibrated_score: 0.2,
    confidence: 0.82,
    uncertainty: 0.14,
    uncertainty_bucket: 'low',
    path_scores: {},
    path_contributors: {},
    content_class: 'news',
    content_class_confidence: 0.76,
    semantic_evidence_route: {
      content_class: 'news',
      class_confidence: 0.76,
      runtime_route: 'high_risk_factual',
      learning_capture_plan: 'full_multimodal_capture',
      adversarial_guard: 'clean',
      mismatch_pressure: 'elevated',
      required_runtime_evidence: ['title', 'description', 'thumbnail', 'channel_history', 'light_spam_check'],
      preserved_learning_evidence: ['title', 'description_snapshot', 'thumbnail_ref', 'feedback'],
      route_reasons: [],
    },
    bias_profile: {
      metrics: {},
      positive_biases: [],
      negative_biases: [],
      guardrail_applied: null,
    },
    verification: {
      status: 'not-requested',
      triggers: [],
      reasons: [],
      review_recommended: false,
    },
    action_decision_basis: {
      threshold_action: 'none',
      final_action: 'none',
      decisive_layer: 'threshold',
      verification_considered: false,
      policy_reason: null,
    },
    policy_mode: 'threshold-default',
    resolved_policy_mode: 'threshold-default',
    artifact_provenance: {},
    recommended_action: 'none',
    reasons: [],
    explanation_id: null,
    explanation_summary: null,
    evidence: [],
    ...overrides,
  };
}

describe('reportFeedbackScoring', () => {
  it('moves reported green and yellow items into the orange review band', () => {
    const score = makeScore({
      risk_score: 0.18,
      path_scores: { history: 0.1772 },
    });
    const adjustment = adjustScoreForReportedContent(score, 'moderate', 0);

    expect(targetTruthScoreAfterReport(score, 'moderate', 0)).toBe(4.9);
    expect(getTruthBand(adjustment.adjustedScore)).toBe('orange');
    expect(adjustment.adjustedScore.recommended_action).toBe('ask-report');
  });

  it('moves reported orange items into the red review band', () => {
    const score = makeScore({
      risk_score: 0.55,
      path_scores: { history: 0.1772 },
      recommended_action: 'badge',
      reasons: ['review'],
      explanation_id: 'exp-orange',
      explanation_summary: 'Review item.',
    });
    const adjustment = adjustScoreForReportedContent(score, 'moderate', 1);

    expect(targetTruthScoreAfterReport(score, 'moderate', 1)).toBe(3.3);
    expect(getTruthBand(adjustment.adjustedScore)).toBe('red');
    expect(adjustment.afterRiskScore).toBeGreaterThanOrEqual(score.risk_score);
  });

  it('weights repeated channel reports into a lower red floor', () => {
    const firstReport = targetTruthScoreAfterReport(
      makeScore({ risk_score: 0.72, recommended_action: 'blur' }),
      'moderate',
      0,
    );
    const repeatedReports = targetTruthScoreAfterReport(
      makeScore({ risk_score: 0.72, recommended_action: 'blur' }),
      'moderate',
      5,
    );

    expect(firstReport).toBe(1.0);
    expect(repeatedReports).toBeLessThan(firstReport);
  });

  it('puts direct remove outcomes in the bottom red range', () => {
    const score = makeScore({
      risk_score: 0.2,
      path_scores: { history: 0.1772 },
    });
    const adjustment = adjustScoreForReportedContent(score, 'remove', 3);

    expect(adjustment.afterTruthScore).toBeLessThanOrEqual(1.0);
    expect(truthScore(adjustment.adjustedScore)).toBeLessThanOrEqual(1.0);
    expect(adjustment.adjustedScore.recommended_action).toBe('hide');
  });
});
