import { describe, expect, it } from 'vitest';

import { annotationBatchSchema } from './annotationBatch';

describe('annotationBatchSchema', () => {
  it('parses annotation batch payloads', () => {
    const result = annotationBatchSchema.parse({
      run_id: 'run-1',
      generated_at: '2026-03-23T00:00:00Z',
      review_queue: [
        {
          item_id: 'item-1',
          title: 'Flag this',
          channel_name: 'Channel One',
          weak_label_score: 0.88,
          content_class: 'news',
          dominant_bias_risk: 'channel_prior_dependency',
          current_labels: { clickbait: true },
          annotator_notes: ['needs adjudication'],
          queue_reason: 'Needs review',
        },
      ],
      hard_negative_queue: [{ item_id: 'item-2', title: 'Do not flag' }],
      disagreement_queue: [],
      class_coverage: { news: 1, music: 1 },
      dominant_bias_coverage: { channel_prior_dependency: 1 },
      annotator_notes_fields: ['weak_label_score'],
      source_batch_path: 'datasets/labels/annotation_batches/run-1.json',
      adjudication_summary: {
        saved_count: 1,
        confirmed_count: 1,
        escalation_count: 0,
        unresolved_count: 0,
        resolution_counts: { 'confirmed-risk': 1 },
        queue_counts: { review: 1 },
        content_class_counts: { news: 1 },
      },
      adjudication_path: 'datasets/labels/adjudication/run-1.json',
      gold_path: 'datasets/labels/gold/run-1-adjudicated.jsonl',
    });

    expect(result.review_queue).toHaveLength(1);
    expect(result.hard_negative_queue).toHaveLength(1);
    expect(result.review_queue[0].channel_name).toBe('Channel One');
    expect(result.review_queue[0].content_class).toBe('news');
    expect(result.review_queue[0].current_labels.clickbait).toBe(true);
    expect(result.class_coverage.news).toBe(1);
    expect(result.adjudication_summary?.saved_count).toBe(1);
  });
});
