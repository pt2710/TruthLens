import { z } from 'zod';

export const recommendedActionSchema = z.enum([
  'none',
  'badge',
  'blur',
  'hide',
  'ask-report',
]);

export const channelInfoSchema = z.object({
  channel_name: z.string().min(1),
  channel_url: z.string().url().optional().nullable(),
  prior_flags: z.number().int().nonnegative().default(0),
});

export const itemMetadataSchema = z.object({
  upload_time: z.string().optional().nullable(),
  duration_seconds: z.number().int().nonnegative().optional().nullable(),
  view_count: z.number().int().nonnegative().optional().nullable(),
  like_count: z.number().int().nonnegative().optional().nullable(),
});

export const scoreItemRequestSchema = z.object({
  item_id: z.string().min(1),
  title: z.string().min(1),
  thumbnail_ref: z.string().optional().nullable(),
  metadata: itemMetadataSchema,
  channel: channelInfoSchema,
});

export const scoreResultSchema = z
  .object({
    risk_score: z.number().min(0).max(1),
    confidence: z.number().min(0).max(1),
    uncertainty: z.number().min(0).max(1),
    recommended_action: recommendedActionSchema,
    reasons: z.array(z.string()),
  })
  .superRefine((value, ctx) => {
    if (value.recommended_action !== 'none' && value.reasons.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Active recommendations require at least one reason.',
        path: ['reasons'],
      });
    }
  });

export const batchScoreRequestSchema = z.object({
  items: z.array(scoreItemRequestSchema).min(1),
});

export const batchScoreResponseSchema = z.object({
  results: z.record(scoreResultSchema),
});

export const feedbackEventSchema = z.object({
  item_id: z.string().min(1),
  item_hash: z.string().optional().nullable(),
  model_version: z.string().min(1),
  policy_version: z.string().min(1),
  action_shown: recommendedActionSchema,
  user_action: z.string().min(1),
  explanation_id: z.string().optional().nullable(),
  before_score: z.number().min(0).max(1).optional().nullable(),
  after_score: z.number().min(0).max(1).optional().nullable(),
  timestamp: z.string().min(1),
});

export const datasetRecordSchema = z.object({
  item_id: z.string(),
  platform: z.string(),
  source_run_id: z.string(),
  source_url: z.string(),
  collected_at: z.string(),
  title: z.string(),
  channel_name: z.string(),
  thumbnail_path: z.string(),
  description: z.string(),
  tags: z.array(z.string()),
  hashtags: z.array(z.string()),
  transcript_excerpt: z.string().nullable().optional(),
  metadata: z.record(z.unknown()),
  history: z.record(z.unknown()),
  features: z.record(z.unknown()),
  labels: z.record(z.unknown()),
  provenance: z.record(z.unknown()),
  annotator_notes: z.array(z.string()),
});

export type RecommendedAction = z.infer<typeof recommendedActionSchema>;
export type ScoreItemRequest = z.infer<typeof scoreItemRequestSchema>;
export type ScoreResult = z.infer<typeof scoreResultSchema>;
export type FeedbackEvent = z.infer<typeof feedbackEventSchema>;
export type DatasetRecord = z.infer<typeof datasetRecordSchema>;
