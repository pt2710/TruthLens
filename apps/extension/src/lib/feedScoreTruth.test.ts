import { describe, expect, it } from 'vitest';
import type { ScoreResult } from '@truthlens/shared-schemas';

import {
  buildChannelHistoryFeatures,
  feedDisplayRiskScore,
  feedHistoryAdjustmentScore,
  getFeedRiskTone,
  priorFlagsFromProfile,
  rawRuntimeRiskScore,
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
      trust_score: 2.88,
    };

    const history = buildChannelHistoryFeatures(profile, {
      taxonomy_hint_news: 0.82,
      music_likelihood: 0.03,
    });

    expect(priorFlagsFromProfile(profile)).toBe(3);
    expect(history.channel_risk_mean).toBe(0.712);
    expect(history.repeat_template_rate).toBe(0.5);
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
    expect(feedDisplayRiskScore(score)).toBe(1.8);
    expect(getFeedRiskTone(score)).toBe('high');
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
    expect(feedDisplayRiskScore(score)).toBe(5.7);
    expect(getFeedRiskTone(score)).toBe('medium');
  });

  it('derives chip tone from feed risk and action severity', () => {
    expect(
      getFeedRiskTone(
        makeScoreResult({
          risk_score: 0.84,
          recommended_action: 'ask-report',
        }),
      ),
    ).toBe('low');
    expect(
      getFeedRiskTone(
        makeScoreResult({
          risk_score: 0.56,
          recommended_action: 'badge',
        }),
      ),
    ).toBe('medium');
    expect(
      getFeedRiskTone(
        makeScoreResult({
          risk_score: 0.18,
          recommended_action: 'none',
        }),
      ),
    ).toBe('high');
    expect(
      rawRuntimeRiskScore(
        makeScoreResult({
          risk_score: 0.84,
        }),
      ),
    ).toBe(8.4);
  });
});
