import { describe, expect, it } from 'vitest';
import { scoreResultSchema } from '@truthlens/shared-schemas';

import type { FeedbackChannelProfile } from './api';
import {
  buildFeedPresentationSnapshot,
  planStableRerankOrder,
} from './feedReranking';
import type { PersonalizationSnapshot } from './personalization';
import type { ReviewPromptDecision } from './reviewPrompts';

function makeProfile(overrides: Partial<FeedbackChannelProfile> = {}): FeedbackChannelProfile {
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
    trust_score: 5,
    ...overrides,
  };
}

function makePersonalization(
  overrides: Partial<PersonalizationSnapshot> = {},
): PersonalizationSnapshot {
  return {
    bucket: 'steady',
    displayScore: 5,
    rankingScore: 5,
    trustScore: 5,
    reportRatio: 0,
    transparentRatio: 0,
    reasons: [],
    ...overrides,
  };
}

function makeReviewPrompt(
  overrides: Partial<ReviewPromptDecision> = {},
): ReviewPromptDecision {
  return {
    workflowMode: 'verify-transparent',
    label: 'Verify transparent',
    reason: 'TruthLens thinks this likely looks transparent.',
    ...overrides,
  };
}

describe('feedReranking', () => {
  it('demotes repeated deceptive channel patterns in the local rerank priority', () => {
    const snapshot = buildFeedPresentationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.71,
        confidence: 0.84,
        uncertainty: 0.16,
        path_scores: { history: 0.61 },
        content_class: 'news',
        content_class_confidence: 0.81,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: ['channel-lock-in-risk'],
          guardrail_applied: 'factual-context-amplifies-mismatch',
        },
        recommended_action: 'blur',
        reasons: ['Example'],
        explanation_id: 'exp-1',
        explanation_summary: 'Example',
        evidence: [],
      }),
      makePersonalization({ rankingScore: 2.2, trustScore: 2.8 }),
      makeProfile({
        channel_name: 'AI Revolution',
        reported_item_count: 3,
        report_count: 3,
        trust_score: 2.8,
      }),
      null,
      false,
    );

    expect(snapshot.truthScore).toBeLessThanOrEqual(3.3);
    expect(snapshot.truthBand).toBe('red');
    expect(snapshot.rerankPriority).toBeLessThan(2.5);
  });

  it('promotes transparent creative content and keeps it out of the negative zone', () => {
    const snapshot = buildFeedPresentationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.12,
        confidence: 0.9,
        uncertainty: 0.1,
        path_scores: { history: 0.18 },
        content_class: 'music',
        content_class_confidence: 0.88,
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
      makePersonalization({ rankingScore: 8.6, trustScore: 8.4, transparentRatio: 0.55 }),
      makeProfile({
        channel_name: 'Context First Media',
        transparent_count: 5,
        scored_item_count: 9,
        trust_score: 8.6,
      }),
      makeReviewPrompt(),
      false,
    );

    expect(snapshot.truthBand).toBe('green');
    expect(snapshot.rerankPriority).toBeGreaterThanOrEqual(8.0);
  });

  it('keeps rerank priority aligned with higher UI truth score', () => {
    const highTrust = buildFeedPresentationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.1,
        confidence: 0.9,
        uncertainty: 0.1,
        path_scores: {},
        content_class: 'music',
        content_class_confidence: 0.88,
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
      makePersonalization({ rankingScore: 8.8 }),
      makeProfile({ trust_score: 8.8 }),
      makeReviewPrompt(),
      false,
    );
    const lowTrust = buildFeedPresentationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.82,
        confidence: 0.9,
        uncertainty: 0.1,
        path_scores: {},
        content_class: 'news',
        content_class_confidence: 0.88,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: ['sensational-overweighting'],
          guardrail_applied: 'factual-context-amplifies-mismatch',
        },
        recommended_action: 'ask-report',
        reasons: ['Example'],
        explanation_id: 'exp-low-trust',
        explanation_summary: 'Example',
        evidence: [],
      }),
      makePersonalization({ rankingScore: 2.1 }),
      makeProfile({ trust_score: 2.1, reported_item_count: 3 }),
      null,
      false,
    );

    expect(highTrust.truthScore).toBeGreaterThan(lowTrust.truthScore);
    expect(highTrust.rerankPriority).toBeGreaterThan(lowTrust.rerankPriority);
  });

  it('does not show a green truth band when the prompt asks for report review', () => {
    const snapshot = buildFeedPresentationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.2,
        confidence: 0.82,
        uncertainty: 0.18,
        path_scores: {},
        content_class: 'satire',
        content_class_confidence: 0.71,
        bias_profile: {
          metrics: {},
          positive_biases: ['ambiguity-aware-caution'],
          negative_biases: ['genre-confusion'],
          guardrail_applied: 'satire-context-prefers-review',
        },
        recommended_action: 'badge',
        reasons: ['Example'],
        explanation_id: 'exp-review',
        explanation_summary: 'Example',
        evidence: [],
      }),
      makePersonalization({ rankingScore: 7.2 }),
      makeProfile({ trust_score: 6.5 }),
      makeReviewPrompt({
        workflowMode: 'report',
        label: 'Review report',
        reason: 'TruthLens wants a human report decision for this feed item.',
      }),
      false,
    );

    expect(snapshot.truthScore).toBe(6.6);
    expect(snapshot.truthBand).toBe('yellow');
    expect(snapshot.feedRiskScore).toBeGreaterThanOrEqual(3.4);
  });

  it('keeps satire above the negative bands when only genre confusion is present', () => {
    const snapshot = buildFeedPresentationSnapshot(
      scoreResultSchema.parse({
        risk_score: 0.45,
        confidence: 0.74,
        uncertainty: 0.22,
        path_scores: { history: 0.22 },
        content_class: 'satire',
        content_class_confidence: 0.76,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: ['genre-confusion'],
          guardrail_applied: 'satire-context-balances-mismatch',
        },
        recommended_action: 'badge',
        reasons: ['Example'],
        explanation_id: 'exp-satire',
        explanation_summary: 'Example',
        evidence: [],
      }),
      makePersonalization({ rankingScore: 4.4 }),
      makeProfile({
        channel_name: 'Satire Desk',
        reported_item_count: 0,
        trust_score: 5.1,
      }),
      null,
      false,
    );

    expect(snapshot.rerankPriority).toBeGreaterThanOrEqual(5.0);
  });

  it('keeps locked sponsored slots fixed while movable cards reorder around them', () => {
    const order = planStableRerankOrder([
      {
        card: 'bad-card',
        originalIndex: 0,
        rerankPriority: 1.2,
        rerankLocked: false,
        truthBand: 'red',
      },
      {
        card: 'sponsored-card',
        originalIndex: 1,
        rerankPriority: 0,
        rerankLocked: true,
        truthBand: 'yellow',
      },
      {
        card: 'good-card',
        originalIndex: 2,
        rerankPriority: 8.9,
        rerankLocked: false,
        truthBand: 'green',
      },
    ]);

    expect(order).toEqual(['good-card', 'sponsored-card', 'bad-card']);
  });
});
