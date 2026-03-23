import { z } from 'zod';

export const queueEntrySchema = z.object({
  item_id: z.string().min(1),
  title: z.string().min(1),
  weak_label_score: z.number().optional(),
  uncertainty_bucket: z.string().optional(),
});

export const annotationBatchSchema = z.object({
  run_id: z.string().min(1),
  review_queue: z.array(queueEntrySchema),
  hard_negative_queue: z.array(queueEntrySchema),
  disagreement_queue: z.array(queueEntrySchema),
  annotator_notes_fields: z.array(z.string()),
});

export type QueueEntry = z.infer<typeof queueEntrySchema>;
export type AnnotationBatch = z.infer<typeof annotationBatchSchema>;

export async function loadAnnotationBatch(): Promise<AnnotationBatch> {
  const response = await fetch('/annotation-batch.json');
  if (!response.ok) {
    throw new Error(`Failed to load annotation batch: ${response.status}`);
  }
  return annotationBatchSchema.parse(await response.json());
}
