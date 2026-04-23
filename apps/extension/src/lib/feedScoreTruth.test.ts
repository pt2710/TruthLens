import { describe, expect, it } from 'vitest';
import type { ScoreResult } from '@truthlens/shared-schemas';

import {
  buildChannelHistoryFeatures,
  feedRiskScore,
  feedHistoryAdjustmentScore,
  getTruthBand,
  priorFlagsFromProfile,
  rawRuntimeRiskScore,
  truthBandFromScore,
  truthScore,
} from './feedScoreTruth';

function makeScoreResult(
  overrides: Partial<ScoreResult> = {},
): ScoreResult {
  return {
    risk_score: 0.2,
    fused_score: 0.2,
    calibrated_score: 0.2,
    confidence: 0.8,
    uncertainty: 0.1,
    uncertainty_bucket: 'low',
    path_scores: {},
    path_contributors: {},
    content_class: 'news',
    content_class_confidence: 0.7,
    bias_profile: {
      metrics: {},
      positive_biases: [],
      negative_biases: [],
      guardrail_applied: null,
    },
    recommended_action: 'none',
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
    reasons: [],
    evidence: [],
    explanation_id: null,
    explanation_summary: null,
    artifact_provenance: {},
    ...overrides,
  };
}

describe('feedScoreTruth', () => {
  it('merges negative channel history into the feed request features', () => {
    const profile = {
      channel_name: 'AI Revolution',
      event_count: 3,
      bias: -0.1,
      report_count: 3,
      dismiss_count: 0,
      mute_count: 0,
      scored_item_count: 6,
      reported_item_count: 3,
      effective_sample_count: 5,
      channel_risk_mean: 0.7208,
      repeat_template_rate: 0.6,
      trust_score: 2.88,
    };

    const history = buildChannelHistoryFeatures(profile, {
      taxonomy_hint_news: 0.82,
      music_likelihood: 0.03,
    });

    expect(priorFlagsFromProfile(profile)).toBe(3);
    expect(history.channel_risk_mean).toBe(0.7208);
    expect(history.repeat_template_rate).toBe(0.6);
    expect(history.effective_sample_count).toBe(5);
    expect(history.taxonomy_hint_news).toBe(0.82);
  });

  it('keeps neutral-history cards anchored to the raw runtime risk', () => {
    const score = makeScoreResult({
      risk_score: 0.18,
      recommended_action: 'none',
      path_scores: {
        history: 0.1772,
      },
    });

    expect(feedHistoryAdjustmentScore(score)).toBe(0);
    expect(feedRiskScore(score)).toBe(1.8);
    expect(truthScore(score)).toBe(8.2);
    expect(getTruthBand(score)).toBe('green');
  });

  it('lifts feed skepticism when negative channel history exceeds the neutral baseline', () => {
    const score = makeScoreResult({
      risk_score: 0.22,
      recommended_action: 'none',
      path_scores: {
        history: 0.5306,
      },
    });

    expect(rawRuntimeRiskScore(score)).toBe(2.2);
    expect(feedHistoryAdjustmentScore(score)).toBe(3.5);
    expect(feedRiskScore(score)).toBe(5.7);
    expect(truthScore(score)).toBe(4.3);
    expect(getTruthBand(score)).toBe('orange');
  });

  it('maps truth scores onto the four product color bands', () => {
    expect(truthBandFromScore(3.3)).toBe('red');
    expect(truthBandFromScore(3.4)).toBe('orange');
    expect(truthBandFromScore(5.0)).toBe('yellow');
    expect(truthBandFromScore(6.7)).toBe('green');
  });
});
