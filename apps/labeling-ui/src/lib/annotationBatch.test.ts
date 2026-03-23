import { describe, expect, it } from 'vitest';

import { annotationBatchSchema } from './annotationBatch';

describe('annotationBatchSchema', () => {
  it('parses annotation batch payloads', () => {
    const result = annotationBatchSchema.parse({
      run_id: 'run-1',
      review_queue: [{ item_id: 'item-1', title: 'Flag this', weak_label_score: 0.88 }],
      hard_negative_queue: [{ item_id: 'item-2', title: 'Do not flag' }],
      disagreement_queue: [],
      annotator_notes_fields: ['weak_label_score'],
    });

    expect(result.review_queue).toHaveLength(1);
    expect(result.hard_negative_queue).toHaveLength(1);
  });
});
