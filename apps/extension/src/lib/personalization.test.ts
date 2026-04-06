import { describe, expect, it } from 'vitest';
import { scoreResultSchema } from '@truthlens/shared-schemas';

import type { FeedbackChannelProfile } from './api';
import {
  buildPersonalizationSnapshot,
  shouldShowPersonalizationBadge,
} from './personalization';

function buildChannelProfile(overrides: Partial<FeedbackChannelProfile>): FeedbackChannelProfile {
  return {
    channel_name: 'Channel',
    event_count: 0,
    bias: 0,
    report_count: 0,
    dismiss_count: 0,
    mute_count: 0,
    transparent_count: 0,
    moderate_request_count: 0,
    remove_request_count: 0,
    scored_item_count: 0,
    reported_item_count: 0,
    trust_score: 5.0,
    ...overrides,
  };
}

describe('buildPersonalizationSnapshot', () => {
  it('boosts high-trust transparent channels when the current item looks consistent', () => {
    const snapshot = buildPersonalizationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.18,
        confidence: 0.84,
        uncertainty: 0.16,
        content_class: 'music',
        content_class_confidence: 0.9,
        bias_profile: {
          metrics: {},
          positive_biases: ['stylistic-divergence-tolerance'],
          negative_biases: [],
          guardrail_applied: 'music-context-dampens-crossmodal-rigidity',
        },
        recommended_action: 'none',
        reasons: [],
        explanation_id: null,
        explanation_summary: null,
        evidence: [],
      }),
      buildChannelProfile({
        channel_name: 'Context First Media',
        trust_score: 8.6,
        transparent_count: 5,
        scored_item_count: 9,
      }),
    );

    expect(snapshot.bucket).toBe('boosted');
    expect(snapshot.rankingScore).toBeGreaterThan(9.0);
    expect(shouldShowPersonalizationBadge(snapshot, scoreResultSchema.parse({
      risk_score: 0.18,
      confidence: 0.84,
      uncertainty: 0.16,
      content_class: 'music',
      content_class_confidence: 0.9,
      bias_profile: {
        metrics: {},
        positive_biases: ['stylistic-divergence-tolerance'],
        negative_biases: [],
        guardrail_applied: 'music-context-dampens-crossmodal-rigidity',
      },
      recommended_action: 'none',
      reasons: [],
      explanation_id: null,
      explanation_summary: null,
      evidence: [],
    }))).toBe(true);
  });

  it('downranks channels with repeated reports and an active misleading recommendation', () => {
    const snapshot = buildPersonalizationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.74,
        confidence: 0.88,
        uncertainty: 0.12,
        content_class: 'news',
        content_class_confidence: 0.88,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: ['sensational-overweighting'],
          guardrail_applied: 'factual-context-amplifies-mismatch',
        },
        recommended_action: 'blur',
        reasons: ['Title contains sensational framing patterns.'],
        explanation_id: 'exp-card-1',
        explanation_summary: 'Flagged because the title framing is sensational.',
        evidence: [],
      }),
      buildChannelProfile({
        channel_name: 'OpenSky Alerts',
        trust_score: 3.4,
        report_count: 3,
        moderate_request_count: 2,
        remove_request_count: 1,
        scored_item_count: 6,
        reported_item_count: 3,
      }),
    );

    expect(snapshot.bucket).toBe('downranked');
    expect(snapshot.rankingScore).toBeLessThan(1.0);
  });

  it('keeps moderate-risk cards steady when the channel history is mixed', () => {
    const snapshot = buildPersonalizationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.44,
        confidence: 0.79,
        uncertainty: 0.21,
        content_class: 'commentary',
        content_class_confidence: 0.71,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: [],
          guardrail_applied: 'argument-context-balances-mismatch',
        },
        recommended_action: 'badge',
        reasons: ['Dynamic card entered the moderate-risk review band.'],
        explanation_id: 'exp-card-dynamic',
        explanation_summary: 'Flagged because the dynamic card entered the moderate-risk review band.',
        evidence: [],
      }),
      buildChannelProfile({
        channel_name: 'Dynamic Signal Desk',
        trust_score: 5.2,
        scored_item_count: 2,
      }),
    );

    expect(snapshot.bucket).toBe('steady');
    expect(snapshot.rankingScore).toBeGreaterThanOrEqual(4.5);
    expect(snapshot.rankingScore).toBeLessThan(7.25);
  });
});
