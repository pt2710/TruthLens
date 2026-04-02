import { describe, expect, it } from 'vitest';

import { inferReviewPromptDecision } from './reviewPrompts';

describe('inferReviewPromptDecision', () => {
  it('suggests a report review for ask-report items', () => {
    const decision = inferReviewPromptDecision(
      {
        risk_score: 0.73,
        confidence: 0.84,
        uncertainty: 0.16,
        recommended_action: 'ask-report',
        reasons: ['reason'],
        explanation_id: 'exp-1',
        explanation_summary: 'summary',
        evidence: [],
      },
      0.08,
    );

    expect(decision).toEqual({
      workflowMode: 'report',
      label: 'Review report',
      reason: 'TruthLens wants a manual clickbait review for this item.',
      autoOpen: true,
    });
  });

  it('suggests transparent verification for low-risk music content', () => {
    const decision = inferReviewPromptDecision(
      {
        risk_score: 0.14,
        confidence: 0.85,
        uncertainty: 0.15,
        recommended_action: 'none',
        reasons: [],
        explanation_id: null,
        explanation_summary: null,
        evidence: [],
      },
      0.92,
    );

    expect(decision).toEqual({
      workflowMode: 'verify-transparent',
      label: 'Verify transparent',
      reason: 'TruthLens thinks this likely looks like transparent music content.',
      autoOpen: true,
    });
  });

  it('returns no prompt for ordinary badge-level items without strong music evidence', () => {
    const decision = inferReviewPromptDecision(
      {
        risk_score: 0.24,
        confidence: 0.78,
        uncertainty: 0.22,
        recommended_action: 'badge',
        reasons: ['reason'],
        explanation_id: 'exp-2',
        explanation_summary: 'summary',
        evidence: [],
      },
      0.12,
    );

    expect(decision).toBeNull();
  });
});
