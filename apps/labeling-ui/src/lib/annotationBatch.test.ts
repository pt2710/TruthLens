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
          queue_reason: 'Needs review',
        },
      ],
      hard_negative_queue: [{ item_id: 'item-2', title: 'Do not flag' }],
      disagreement_queue: [],
      annotator_notes_fields: ['weak_label_score'],
      source_batch_path: 'datasets/labels/annotation_batches/run-1.json',
    });

    expect(result.review_queue).toHaveLength(1);
    expect(result.hard_negative_queue).toHaveLength(1);
    expect(result.review_queue[0].channel_name).toBe('Channel One');
  });
});
