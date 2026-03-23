import { z } from 'zod';

export const queueEntrySchema = z.object({
  item_id: z.string().min(1),
  title: z.string().min(1),
  channel_name: z.string().min(1).optional(),
  weak_label_score: z.number().optional(),
  uncertainty_bucket: z.string().optional(),
  source_trust_flag: z.string().optional(),
  template_cluster: z.string().optional(),
  prior_flags: z.number().int().nonnegative().optional(),
  queue_reason: z.string().optional(),
});

export const annotationBatchSchema = z.object({
  run_id: z.string().min(1),
  generated_at: z.string().optional(),
  review_queue: z.array(queueEntrySchema),
  hard_negative_queue: z.array(queueEntrySchema),
  disagreement_queue: z.array(queueEntrySchema),
  annotator_notes_fields: z.array(z.string()),
  source_batch_path: z.string().optional(),
});

export type QueueEntry = z.infer<typeof queueEntrySchema>;
export type AnnotationBatch = z.infer<typeof annotationBatchSchema>;

export async function loadAnnotationBatch(): Promise<AnnotationBatch> {
  const response = await fetch('/annotation-batch.data.json');
  if (!response.ok) {
    throw new Error(`Failed to load annotation batch: ${response.status}`);
  }
  return annotationBatchSchema.parse(await response.json());
}
