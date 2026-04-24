import { describe, expect, it } from 'vitest';
import { scoreResultSchema } from '@truthlens/shared-schemas';

import { inferReviewPromptDecision } from './reviewPrompts';

describe('inferReviewPromptDecision', () => {
  it('suggests a report review for ask-report items', () => {
    const decision = inferReviewPromptDecision(
      scoreResultSchema.parse({
        risk_score: 0.73,
        confidence: 0.84,
        uncertainty: 0.16,
        content_class: 'news',
        content_class_confidence: 0.84,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: ['sensational-overweighting'],
          guardrail_applied: 'factual-context-amplifies-mismatch',
        },
        recommended_action: 'ask-report',
        reasons: ['reason'],
        explanation_id: 'exp-1',
        explanation_summary: 'summary',
        evidence: [],
      }),
      0.08,
    );

    expect(decision).toEqual({
      workflowMode: 'report',
      label: 'Review report',
      reason: 'TruthLens wants a manual clickbait review for this item.',
    });
  });

  it('suggests transparent verification for low-risk music content', () => {
    const decision = inferReviewPromptDecision(
      scoreResultSchema.parse({
        risk_score: 0.14,
        confidence: 0.85,
        uncertainty: 0.15,
        content_class: 'music',
        content_class_confidence: 0.92,
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
      0.92,
    );

    expect(decision).toEqual({
      workflowMode: 'verify-transparent',
      label: 'Verify transparent',
      reason: 'TruthLens thinks this likely looks like transparent music content.',
    });
  });

  it('returns no prompt for ordinary badge-level items without strong music evidence', () => {
    const decision = inferReviewPromptDecision(
      scoreResultSchema.parse({
        risk_score: 0.24,
        confidence: 0.78,
        uncertainty: 0.22,
        content_class: 'commentary',
        content_class_confidence: 0.66,
        bias_profile: {
          metrics: {},
          positive_biases: ['factual-scrutiny'],
          negative_biases: [],
          guardrail_applied: 'argument-context-balances-mismatch',
        },
        recommended_action: 'badge',
        reasons: ['reason'],
        explanation_id: 'exp-2',
        explanation_summary: 'summary',
        evidence: [],
      }),
      0.12,
    );

    expect(decision).toBeNull();
  });

  it('routes satire-like ambiguity into a review prompt instead of silent verification', () => {
    const decision = inferReviewPromptDecision(
      scoreResultSchema.parse({
        risk_score: 0.29,
        confidence: 0.71,
        uncertainty: 0.31,
        content_class: 'satire',
        content_class_confidence: 0.68,
        bias_profile: {
          metrics: {},
          positive_biases: ['ambiguity-aware-caution'],
          negative_biases: ['genre-confusion'],
          guardrail_applied: 'satire-context-prefers-review',
        },
        recommended_action: 'badge',
        reasons: ['reason'],
        explanation_id: 'exp-3',
        explanation_summary: 'summary',
        evidence: [],
      }),
      0.08,
    );

    expect(decision).toEqual({
      workflowMode: 'report',
      label: 'Review ambiguity',
      reason: 'TruthLens sees satire-like or ambiguous packaging that still needs human confirmation.',
    });
  });
});
