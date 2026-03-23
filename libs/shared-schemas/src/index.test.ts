import { describe, expect, it } from 'vitest';

import { datasetRecordSchema, scoreResultSchema } from './index';

describe('shared schemas', () => {
  it('requires reasons for active recommendations', () => {
    const result = scoreResultSchema.safeParse({
      risk_score: 0.8,
      confidence: 0.9,
      uncertainty: 0.1,
      recommended_action: 'blur',
      reasons: [],
      explanation_id: null,
      explanation_summary: null,
      evidence: [],
    });

    expect(result.success).toBe(false);
  });

  it('accepts structured explanation payloads for active recommendations', () => {
    const result = scoreResultSchema.safeParse({
      risk_score: 0.8,
      confidence: 0.9,
      uncertainty: 0.1,
      recommended_action: 'blur',
      reasons: ['Title contains strong sensational framing patterns.'],
      explanation_id: 'exp-item-1',
      explanation_summary: 'Flagged because the title framing is sensational and the thumbnail pattern is exaggerated.',
      evidence: [
        {
          kind: 'title',
          label: 'Sensational title framing',
          score: 0.88,
          details: 'Multiple high-intensity claim tokens were detected in the title.',
        },
      ],
    });

    expect(result.success).toBe(true);
  });

  it('validates canonical dataset records', () => {
    const result = datasetRecordSchema.safeParse({
      item_id: 'item-1',
      platform: 'youtube',
      source_run_id: 'run-1',
      source_url: 'https://youtube.com/watch?v=123',
      collected_at: '2026-03-22T00:00:00Z',
      title: 'Breaking aliens confirmed',
      channel_name: 'TruthLens Test',
      thumbnail_path: 'datasets/raw/thumbnails/item-1.jpg',
      description: 'Description',
      tags: ['news'],
      hashtags: ['#breaking'],
      transcript_excerpt: null,
      metadata: {},
      history: {},
      features: {},
      labels: {},
      provenance: {},
      annotator_notes: [],
    });

    expect(result.success).toBe(true);
  });
});
