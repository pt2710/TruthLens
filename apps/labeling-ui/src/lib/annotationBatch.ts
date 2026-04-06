import { z } from 'zod';

const API_BASE = (import.meta.env.VITE_TRUTHLENS_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000';

export const annotationQueueNameSchema = z.enum(['review', 'hard-negative', 'disagreement']);
export const annotationResolutionSchema = z.enum([
  'confirmed-risk',
  'confirmed-benign',
  'needs-escalation',
]);

export const adjudicationDecisionSchema = z.object({
  item_id: z.string().min(1),
  queue_name: annotationQueueNameSchema,
  resolution: annotationResolutionSchema,
  content_class: z.string().min(1).default('unknown'),
  label_overrides: z.record(z.boolean()).default({}),
  bias_review_required: z.boolean().optional().nullable(),
  reviewer: z.string().optional().nullable(),
  note: z.string().optional().nullable(),
  decided_at: z.string().optional().nullable(),
});

export const queueEntrySchema = z.object({
  item_id: z.string().min(1),
  title: z.string().min(1),
  channel_name: z.string().min(1).optional(),
  weak_label_score: z.number().optional(),
  uncertainty_bucket: z.string().optional(),
  source_trust_flag: z.string().optional(),
  template_cluster: z.string().optional(),
  prior_flags: z.number().int().nonnegative().optional(),
  content_class: z.string().optional(),
  content_class_confidence: z.number().optional(),
  dominant_bias_risk: z.string().optional(),
  bias_review_required: z.boolean().optional(),
  current_labels: z.record(z.boolean()).default({}),
  annotator_notes: z.array(z.string()).default([]),
  adjudication: adjudicationDecisionSchema.optional(),
  queue_reason: z.string().optional(),
});

export const annotationBatchSchema = z.object({
  run_id: z.string().min(1),
  generated_at: z.string().optional(),
  review_queue: z.array(queueEntrySchema),
  hard_negative_queue: z.array(queueEntrySchema),
  disagreement_queue: z.array(queueEntrySchema),
  class_coverage: z.record(z.number().int().nonnegative()).default({}),
  dominant_bias_coverage: z.record(z.number().int().nonnegative()).default({}),
  annotator_notes_fields: z.array(z.string()),
  source_batch_path: z.string().optional(),
  adjudication_summary: z
    .object({
      saved_count: z.number().int().nonnegative().default(0),
      confirmed_count: z.number().int().nonnegative().default(0),
      escalation_count: z.number().int().nonnegative().default(0),
      unresolved_count: z.number().int().nonnegative().default(0),
      resolution_counts: z.record(z.number().int().nonnegative()).default({}),
      queue_counts: z.record(z.number().int().nonnegative()).default({}),
      content_class_counts: z.record(z.number().int().nonnegative()).default({}),
    })
    .optional(),
  adjudication_path: z.string().optional(),
  gold_path: z.string().optional(),
});

export const saveAnnotationAdjudicationsRequestSchema = z.object({
  run_id: z.string().min(1),
  reviewer: z.string().optional().nullable(),
  decisions: z.array(adjudicationDecisionSchema),
});

export const saveAnnotationAdjudicationsResponseSchema = z.object({
  run_id: z.string().min(1),
  saved_at: z.string().min(1),
  saved_count: z.number().int().nonnegative(),
  adjudication_path: z.string().min(1),
  gold_path: z.string().min(1),
  summary: z.record(z.unknown()),
});

export type AnnotationQueueName = z.infer<typeof annotationQueueNameSchema>;
export type AnnotationResolution = z.infer<typeof annotationResolutionSchema>;
export type AnnotationDecision = z.infer<typeof adjudicationDecisionSchema>;
export type QueueEntry = z.infer<typeof queueEntrySchema>;
export type AnnotationBatch = z.infer<typeof annotationBatchSchema>;
export type SaveAnnotationAdjudicationsRequest = z.infer<typeof saveAnnotationAdjudicationsRequestSchema>;
export type SaveAnnotationAdjudicationsResponse = z.infer<typeof saveAnnotationAdjudicationsResponseSchema>;

export async function loadAnnotationBatch(): Promise<AnnotationBatch> {
  try {
    const response = await fetch(`${API_BASE}/annotation-batch/latest`);
    if (!response.ok) {
      throw new Error(`Failed to load annotation batch from API: ${response.status}`);
    }
    return annotationBatchSchema.parse(await response.json());
  } catch {
    const response = await fetch('/annotation-batch.data.json');
    if (!response.ok) {
      throw new Error(`Failed to load annotation batch: ${response.status}`);
    }
    return annotationBatchSchema.parse(await response.json());
  }
}

export async function saveAnnotationAdjudications(
  payload: SaveAnnotationAdjudicationsRequest,
): Promise<SaveAnnotationAdjudicationsResponse> {
  const parsedPayload = saveAnnotationAdjudicationsRequestSchema.parse(payload);
  const response = await fetch(`${API_BASE}/annotation-batch/adjudications`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(parsedPayload),
  });
  if (!response.ok) {
    let detail = `Failed to save adjudications: ${response.status}`;
    try {
      const errorPayload = (await response.json()) as { detail?: string };
      if (errorPayload.detail) {
        detail = errorPayload.detail;
      }
    } catch {
      // Keep the HTTP status fallback message.
    }
    throw new Error(detail);
  }
  return saveAnnotationAdjudicationsResponseSchema.parse(await response.json());
}
