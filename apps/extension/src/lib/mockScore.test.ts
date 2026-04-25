import { describe, expect, it } from 'vitest';
import { scoreItemRequestSchema } from '@truthlens/shared-schemas';

import { createBootstrapScore } from './mockScore';

describe('createBootstrapScore', () => {
  it('flags sensational titles', () => {
    const result = createBootstrapScore(scoreItemRequestSchema.parse({
      item_id: 'card-1',
      title: 'Breaking secret aliens confirmed',
      thumbnail_ref: null,
      transcript_excerpt: null,
      metadata: {},
      channel: {
        channel_name: 'Channel',
        prior_flags: 1,
        channel_history_features: {},
      },
      user_context: {
        strict_mode: false,
        muted_channels: [],
        prior_corrections: 0,
      },
    }));

    expect(result.risk_score).toBeGreaterThan(0.35);
    expect(result.reasons.length).toBeGreaterThan(0);
    expect(result.explanation_id).toBeTruthy();
    expect(result.evidence.length).toBeGreaterThan(0);
    expect(result.content_class).toBe('news');
    expect(result.bias_profile.metrics.sensational_weight).toBeGreaterThan(0);
  });

  it('hides muted channels immediately', () => {
    const result = createBootstrapScore(scoreItemRequestSchema.parse({
      item_id: 'card-2',
      title: 'Weekly launch schedule',
      thumbnail_ref: null,
      transcript_excerpt: null,
      metadata: {},
      channel: {
        channel_name: 'Muted Channel',
        prior_flags: 0,
        channel_history_features: {},
      },
      user_context: {
        strict_mode: false,
        muted_channels: ['Muted Channel'],
        prior_corrections: 0,
      },
    }));

    expect(result.recommended_action).toBe('hide');
    expect(result.reasons[0]).toContain('muted');
    expect(result.explanation_summary).toContain('muted');
  });

  it('detects music uploads from beat and instrumental framing', () => {
    const result = createBootstrapScore(scoreItemRequestSchema.parse({
      item_id: 'card-3',
      title: 'Night Drive Type Beat - Neon Instrumental',
      description_snapshot: 'Atmospheric instrumental beat for coding and writing.',
      thumbnail_ref: null,
      transcript_excerpt: null,
      metadata: {},
      channel: {
        channel_name: 'Nova Beats',
        prior_flags: 0,
        channel_history_features: {},
      },
      user_context: {
        strict_mode: false,
        muted_channels: [],
        prior_corrections: 0,
      },
    }));

    expect(result.content_class).toBe('music');
    expect(result.content_class_confidence).toBeGreaterThan(0.7);
  });

  it('detects art uploads from gallery and sketchbook framing', () => {
    const result = createBootstrapScore(scoreItemRequestSchema.parse({
      item_id: 'card-4',
      title: 'Fragments of Blue - Sketchbook Process',
      description_snapshot: 'Sketchbook process and gallery prep notes for the exhibition piece.',
      thumbnail_ref: null,
      transcript_excerpt: null,
      metadata: {},
      channel: {
        channel_name: 'North Gallery Studio',
        prior_flags: 0,
        channel_history_features: {},
      },
      user_context: {
        strict_mode: false,
        muted_channels: [],
        prior_corrections: 0,
      },
    }));

    expect(result.content_class).toBe('art');
    expect(result.content_class_confidence).toBeGreaterThan(0.7);
  });
});
