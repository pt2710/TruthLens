import { z } from 'zod';

export const recommendedActionSchema = z.enum([
  'none',
  'badge',
  'blur',
  'hide',
  'ask-report',
]);

export const contentClassSchema = z.enum([
  'news',
  'commentary',
  'documentary',
  'music',
  'art',
  'satire',
  'gaming',
  'promo',
  'unknown',
]);

export const channelInfoSchema = z.object({
  channel_name: z.string().min(1),
  channel_url: z.string().url().optional().nullable(),
  prior_flags: z.number().int().nonnegative().default(0),
  channel_history_features: z.record(z.number()).default({}),
});

export const itemMetadataSchema = z.object({
  upload_time: z.string().optional().nullable(),
  duration_seconds: z.number().int().nonnegative().optional().nullable(),
  view_count: z.number().int().nonnegative().optional().nullable(),
  like_count: z.number().int().nonnegative().optional().nullable(),
});

export const userContextSchema = z.object({
  strict_mode: z.boolean().default(false),
  muted_channels: z.array(z.string()).default([]),
  prior_corrections: z.number().int().nonnegative().default(0),
});

export const runtimeContextSchema = z.object({
  surface: z
    .enum(['extension-feed', 'extension-watch', 'mobile-share', 'api', 'trainer', 'unknown'])
    .default('unknown'),
  review_requested: z.boolean().default(false),
  source_provenance: z.string().optional().nullable(),
});

export const observationDistilledFeaturesSchema = z.object({
  card_index: z.number().int().nonnegative().optional().nullable(),
  link_kind: z.enum(['watch', 'shorts', 'other', 'unknown']).default('unknown'),
  has_thumbnail: z.boolean().default(false),
  has_description_snapshot: z.boolean().default(false),
  has_transcript_excerpt: z.boolean().default(false),
  title_token_count: z.number().int().nonnegative().default(0),
  description_token_count: z.number().int().nonnegative().default(0),
  channel_known: z.boolean().default(true),
  duration_seconds: z.number().int().nonnegative().optional().nullable(),
});

export const observationScoreSnapshotSchema = z.object({
  risk_score: z.number().min(0).max(1).default(0),
  calibrated_score: z.number().min(0).max(1).default(0),
  uncertainty: z.number().min(0).max(1).default(0),
  recommended_action: recommendedActionSchema.default('none'),
  content_class: contentClassSchema.default('unknown'),
  content_class_confidence: z.number().min(0).max(1).default(0),
  explanation_id: z.string().optional().nullable(),
});

export const observationProvenanceSchema = z.object({
  observed_at: z.string().min(1),
  collector: z.enum(['extension-dom', 'api', 'unknown']).default('unknown'),
  collector_version: z.string().optional().nullable(),
  session_id: z.string().optional().nullable(),
  page_url: z.string().optional().nullable(),
  source_path: z.string().optional().nullable(),
});

export const browserObservationRecordSchema = z.object({
  observation_id: z.string().min(1),
  item_id: z.string().min(1),
  item_hash: z.string().optional().nullable(),
  title_snapshot: z.string().min(1),
  channel_name: z.string().optional().nullable(),
  channel_url: z.string().url().optional().nullable(),
  link_url: z.string().url().optional().nullable(),
  thumbnail_ref: z.string().optional().nullable(),
  description_snapshot: z.string().optional().nullable(),
  transcript_excerpt: z.string().optional().nullable(),
  metadata: itemMetadataSchema.default({}),
  runtime_context: runtimeContextSchema.default({
    surface: 'unknown',
    review_requested: false,
    source_provenance: null,
  }),
  distilled_features: observationDistilledFeaturesSchema.default({
    link_kind: 'unknown',
    has_thumbnail: false,
    has_description_snapshot: false,
    has_transcript_excerpt: false,
    title_token_count: 0,
    description_token_count: 0,
    channel_known: true,
  }),
  score_snapshot: observationScoreSnapshotSchema.default({
    risk_score: 0,
    calibrated_score: 0,
    uncertainty: 0,
    recommended_action: 'none',
    content_class: 'unknown',
    content_class_confidence: 0,
    explanation_id: null,
  }),
  provenance: observationProvenanceSchema,
});

export const scoreItemRequestSchema = z.object({
  item_id: z.string().min(1),
  title: z.string().min(1),
  thumbnail_ref: z.string().optional().nullable(),
  description_snapshot: z.string().optional().nullable(),
  transcript_excerpt: z.string().optional().nullable(),
  metadata: itemMetadataSchema,
  channel: channelInfoSchema,
  user_context: userContextSchema.default({
    strict_mode: false,
    muted_channels: [],
    prior_corrections: 0,
  }),
  runtime_context: runtimeContextSchema.default({
    surface: 'unknown',
    review_requested: false,
    source_provenance: null,
  }),
});

export const explanationEvidenceSchema = z.object({
  kind: z.enum([
    'title',
    'thumbnail',
    'history',
    'transcript',
    'metadata',
    'policy',
    'taxonomy',
    'bias',
    'verification',
    'user-context',
    'uncertainty',
  ]),
  label: z.string().min(1),
  score: z.number().min(0).max(1).optional().nullable(),
  details: z.string().optional().nullable(),
});

export const biasProfileSchema = z.object({
  metrics: z.record(z.number()).default({}),
  positive_biases: z.array(z.string()).default([]),
  negative_biases: z.array(z.string()).default([]),
  guardrail_applied: z.string().optional().nullable(),
});

export const verificationStatusSchema = z.enum([
  'not-requested',
  'completed',
  'failed-soft',
]);

export const verificationTriggerSchema = z.enum([
  'high-risk',
  'high-uncertainty',
  'high-mismatch',
  'threshold-near',
  'review-flow',
]);

export const verificationProvenanceSchema = z.object({
  status: verificationStatusSchema.default('not-requested'),
  triggers: z.array(verificationTriggerSchema).default([]),
  reasons: z.array(z.string()).default([]),
  summary: z.string().optional().nullable(),
  review_recommended: z.boolean().default(false),
});

export const actionDecisionBasisSchema = z.object({
  threshold_action: recommendedActionSchema.default('none'),
  final_action: recommendedActionSchema.default('none'),
  decisive_layer: z.enum(['threshold', 'bseo-live', 'muted-channel']).default('threshold'),
  verification_considered: z.boolean().default(false),
  policy_reason: z.string().optional().nullable(),
});

export const artifactProvenanceSchema = z.object({
  model_version: z.string().optional().nullable(),
  model_build_id: z.string().optional().nullable(),
  policy_version: z.string().optional().nullable(),
  policy_build_id: z.string().optional().nullable(),
  policy_artifact_status: z.string().optional().nullable(),
});

export const labelCandidateFeedbackSummarySchema = z.object({
  total_events: z.number().int().nonnegative().default(0),
  risk_event_count: z.number().int().nonnegative().default(0),
  benign_event_count: z.number().int().nonnegative().default(0),
  manual_report_count: z.number().int().nonnegative().default(0),
  last_user_action: z.string().optional().nullable(),
});

export const labelCandidateSplitSafetySchema = z.object({
  dataset_membership: z
    .enum(['existing-batch', 'supplemental-intake', 'supplemental-adjudicated'])
    .default('supplemental-intake'),
  split_status: z
    .enum(['assigned', 'blocked-until-ingestion', 'excluded-from-training'])
    .default('blocked-until-ingestion'),
  split_name: z.enum(['train', 'validation', 'test', 'unknown']).default('unknown'),
  dataset_build_id: z.string().optional().nullable(),
  annotation_run_id: z.string().optional().nullable(),
  eligible_for_training: z.boolean().default(false),
  leakage_guard_reason: z.string().optional().nullable(),
});

export const labelCandidateProvenanceSchema = z.object({
  generated_at: z.string().min(1),
  generator: z.string().default('browser-feedback-intake-v1'),
  candidate_sources: z
    .array(z.enum(['pipeline-batch', 'browser-observation', 'feedback-event', 'manual-report']))
    .default([]),
  observation_ids: z.array(z.string()).default([]),
  feedback_event_ids: z.array(z.string()).default([]),
  source_paths: z.array(z.string()).default([]),
});

export const labelCandidateQueueSchema = z.enum(['review', 'hard-negative', 'disagreement']);

export const labelCandidateSchema = z.object({
  candidate_id: z.string().min(1),
  item_id: z.string().min(1),
  queue_name: labelCandidateQueueSchema,
  origin: z.enum(['pipeline-batch', 'supplemental-intake']).default('pipeline-batch'),
  title: z.string().min(1),
  channel_name: z.string().optional().nullable(),
  weak_label_score: z.number().min(0).max(1).optional().nullable(),
  uncertainty_bucket: z.string().optional().nullable(),
  source_trust_flag: z.string().optional().nullable(),
  template_cluster: z.string().optional().nullable(),
  prior_flags: z.number().int().nonnegative().optional().nullable(),
  content_class: z.string().default('unknown'),
  content_class_confidence: z.number().min(0).max(1).optional().nullable(),
  dominant_bias_risk: z.string().optional().nullable(),
  bias_review_required: z.boolean().optional().nullable(),
  current_labels: z.record(z.boolean()).default({}),
  annotator_notes: z.array(z.string()).default([]),
  queue_reason: z.string().optional().nullable(),
  distilled_features: observationDistilledFeaturesSchema.optional().nullable(),
  feedback_summary: labelCandidateFeedbackSummarySchema.default({
    total_events: 0,
    risk_event_count: 0,
    benign_event_count: 0,
    manual_report_count: 0,
    last_user_action: null,
  }),
  provenance: labelCandidateProvenanceSchema,
  split_safety: labelCandidateSplitSafetySchema.default({
    dataset_membership: 'supplemental-intake',
    split_status: 'blocked-until-ingestion',
    split_name: 'unknown',
    dataset_build_id: null,
    annotation_run_id: null,
    eligible_for_training: false,
    leakage_guard_reason: null,
  }),
});

export const manualReportIssueTypeSchema = z.enum([
  'thumbnail',
  'title',
  'description',
  'transcript',
  'channel',
  'other',
]);

export const manualReportWorkflowModeSchema = z.enum([
  'report',
  'verify-transparent',
]);
export const manualReportRequestedOutcomeSchema = z.enum([
  'moderate',
  'remove',
]);

export const manualReportIssueSchema = z.object({
  issue_type: manualReportIssueTypeSchema,
  comment: z.string().min(1),
  original_comment: z.string().optional().nullable(),
});

export const manualReportSchema = z.object({
  workflow_mode: manualReportWorkflowModeSchema.default('report'),
  target_url: z.string().url().optional().nullable(),
  thumbnail_ref: z.string().optional().nullable(),
  title_snapshot: z.string().min(1),
  transcript_excerpt: z.string().optional().nullable(),
  issues: z.array(manualReportIssueSchema).min(1),
  requested_outcome: manualReportRequestedOutcomeSchema.default('moderate'),
  optimize_requested: z.boolean().default(false),
  optimize_applied: z.boolean().default(false),
  optimization_model: z.string().optional().nullable(),
  report_text: z.string().min(1),
});

export const manualReportOptimizationRequestSchema = z.object({
  workflow_mode: manualReportWorkflowModeSchema.default('report'),
  target_url: z.string().url().optional().nullable(),
  title_snapshot: z.string().min(1),
  channel_name: z.string().min(1),
  transcript_excerpt: z.string().optional().nullable(),
  requested_outcome: manualReportRequestedOutcomeSchema.default('moderate'),
  issues: z
    .array(
      z.object({
        issue_type: manualReportIssueTypeSchema,
        comment: z.string().min(1),
      }),
    )
    .min(1),
});

export const manualReportOptimizationResponseSchema = z.object({
  issues: z.array(
    z.object({
      issue_type: manualReportIssueTypeSchema,
      comment: z.string().min(1),
    }),
  ),
  optimization_model: z.string().min(1),
  report_text: z.string().min(1),
});

export const manualReportSuggestionIssueSchema = z.object({
  issue_type: manualReportIssueTypeSchema,
  suggested: z.boolean(),
  comment: z.string(),
});

export const manualReportSuggestionRequestSchema = z.object({
  workflow_mode: manualReportWorkflowModeSchema.default('report'),
  target_url: z.string().url().optional().nullable(),
  thumbnail_ref: z.string().optional().nullable(),
  title_snapshot: z.string().min(1),
  channel_name: z.string().min(1),
  channel_url: z.string().url().optional().nullable(),
  channel_context: z.string().optional().nullable(),
  description_snapshot: z.string().optional().nullable(),
  transcript_excerpt: z.string().optional().nullable(),
  transcript_available: z.boolean().optional().nullable(),
  explanation_summary: z.string().optional().nullable(),
  reasons: z.array(z.string()).default([]),
  content_class: contentClassSchema.default('unknown'),
  content_class_confidence: z.number().min(0).max(1).default(0),
  bias_profile: biasProfileSchema.default({
    metrics: {},
    positive_biases: [],
    negative_biases: [],
    guardrail_applied: null,
  }),
});

export const manualReportSuggestionResponseSchema = z.object({
  issues: z.array(manualReportSuggestionIssueSchema).length(6),
  suggested_outcome: manualReportRequestedOutcomeSchema,
  suggestion_model: z.string().min(1),
});

export const reviewPromptStateSchema = z.object({
  workflow_mode: manualReportWorkflowModeSchema,
  label: z.string().min(1),
  reason: z.string().min(1),
  auto_open: z.boolean().default(false),
});

export const reviewStatusEventSchema = z.object({
  phase: z.enum([
    'resolve-share',
    'fetch-watch-metadata',
    'score-item',
    'draft-review',
    'youtube-auth',
  ]),
  label: z.string().min(1),
  status: z.literal('completed'),
  details: z.string().optional().nullable(),
});

export const explanationBundlePayloadSchema = z.object({
  explanation_id: z.string().optional().nullable(),
  explanation_summary: z.string().optional().nullable(),
  reasons: z.array(z.string()).default([]),
  evidence: z.array(explanationEvidenceSchema).default([]),
});

export const mobileResolvedWatchContextSchema = z.object({
  target_url: z.string().min(1),
  video_id: z.string().min(1),
  title: z.string().min(1),
  thumbnail_ref: z.string().optional().nullable(),
  channel_name: z.string().min(1),
  channel_url: z.string().optional().nullable(),
  description_snapshot: z.string().optional().nullable(),
  transcript_excerpt: z.string().optional().nullable(),
  transcript_available: z.boolean().default(false),
  channel_context: z.string().optional().nullable(),
  music_likelihood: z.number().min(0).max(1).default(0),
  content_class: contentClassSchema.default('unknown'),
  content_class_confidence: z.number().min(0).max(1).default(0),
  metadata: itemMetadataSchema.default({}),
});

export const mobileAnalyzeShareRequestSchema = z.object({
  target_url: z.string().min(1),
  user_context: userContextSchema.default({
    strict_mode: false,
    muted_channels: [],
    prior_corrections: 0,
  }),
});

export const mobileAnalyzeShareResponseSchema = z.object({
  model_version: z.string().min(1),
  policy_version: z.string().min(1),
  watch_context: mobileResolvedWatchContextSchema,
  score: z.lazy(() => scoreResultSchema),
  explanation: explanationBundlePayloadSchema,
  review_prompt: reviewPromptStateSchema.optional().nullable(),
  draft_suggestion: manualReportSuggestionResponseSchema,
  youtube_auth: z.lazy(() => youtubeAuthStatusSchema),
  status_stream: z.array(reviewStatusEventSchema).default([]),
});

export const youtubeAuthStatusSchema = z.object({
  configured: z.boolean(),
  connected: z.boolean(),
  auth_url: z.string().url().optional().nullable(),
  channel_name: z.string().optional().nullable(),
});

export const youtubeReportRequestSchema = z.object({
  target_url: z.string().url(),
  report_text: z.string().min(1),
  issue_types: z.array(manualReportIssueTypeSchema).min(1),
});

export const youtubeReportResponseSchema = z.object({
  status: z.literal('reported'),
  reason_id: z.string().min(1),
  reason_label: z.string().min(1),
  secondary_reason_id: z.string().optional().nullable(),
  secondary_reason_label: z.string().optional().nullable(),
});

export const scoreResultSchema = z
  .object({
    risk_score: z.number().min(0).max(1),
    fused_score: z.number().min(0).max(1).default(0),
    calibrated_score: z.number().min(0).max(1).default(0),
    confidence: z.number().min(0).max(1),
    uncertainty: z.number().min(0).max(1),
    uncertainty_bucket: z.enum(['low', 'medium', 'high']).default('low'),
    path_scores: z.record(z.number()).default({}),
    path_contributors: z.record(z.array(z.string())).default({}),
    content_class: contentClassSchema.default('unknown'),
    content_class_confidence: z.number().min(0).max(1).default(0),
    bias_profile: biasProfileSchema.default({
      metrics: {},
      positive_biases: [],
      negative_biases: [],
      guardrail_applied: null,
    }),
    verification: verificationProvenanceSchema.default({
      status: 'not-requested',
      triggers: [],
      reasons: [],
      summary: null,
      review_recommended: false,
    }),
    action_decision_basis: actionDecisionBasisSchema.default({
      threshold_action: 'none',
      final_action: 'none',
      decisive_layer: 'threshold',
      verification_considered: false,
      policy_reason: null,
    }),
    policy_mode: z.string().default('threshold-default'),
    resolved_policy_mode: z.string().default('threshold-default'),
    artifact_provenance: artifactProvenanceSchema.default({
      model_version: null,
      model_build_id: null,
      policy_version: null,
      policy_build_id: null,
      policy_artifact_status: null,
    }),
    recommended_action: recommendedActionSchema,
    reasons: z.array(z.string()),
    explanation_id: z.string().optional().nullable(),
    explanation_summary: z.string().optional().nullable(),
    evidence: z.array(explanationEvidenceSchema).default([]),
  })
  .superRefine((value, ctx) => {
    if (value.recommended_action !== 'none' && value.reasons.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Active recommendations require at least one reason.',
        path: ['reasons'],
      });
    }
    if (value.recommended_action !== 'none' && !value.explanation_id) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Active recommendations require an explanation_id.',
        path: ['explanation_id'],
      });
    }
    if (value.recommended_action !== 'none' && !value.explanation_summary) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Active recommendations require an explanation_summary.',
        path: ['explanation_summary'],
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
  feedback_id: z.string().optional().nullable(),
  item_id: z.string().min(1),
  item_hash: z.string().optional().nullable(),
  observation_id: z.string().optional().nullable(),
  channel_name: z.string().optional().nullable(),
  model_version: z.string().min(1),
  policy_version: z.string().min(1),
  action_shown: recommendedActionSchema,
  user_action: z.string().min(1),
  explanation_id: z.string().optional().nullable(),
  before_score: z.number().min(0).max(1).optional().nullable(),
  after_score: z.number().min(0).max(1).optional().nullable(),
  timestamp: z.string().min(1),
  runtime_context: runtimeContextSchema.optional().nullable(),
  artifact_provenance: artifactProvenanceSchema.optional().nullable(),
  manual_report: manualReportSchema.optional().nullable(),
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
export type ContentClass = z.infer<typeof contentClassSchema>;
export type BatchScoreRequest = z.infer<typeof batchScoreRequestSchema>;
export type BatchScoreResponse = z.infer<typeof batchScoreResponseSchema>;
export type ScoreItemRequest = z.infer<typeof scoreItemRequestSchema>;
export type ScoreResult = z.infer<typeof scoreResultSchema>;
export type ExplanationEvidence = z.infer<typeof explanationEvidenceSchema>;
export type BiasProfile = z.infer<typeof biasProfileSchema>;
export type FeedbackEvent = z.infer<typeof feedbackEventSchema>;
export type DatasetRecord = z.infer<typeof datasetRecordSchema>;
export type UserContext = z.infer<typeof userContextSchema>;
export type RuntimeContext = z.infer<typeof runtimeContextSchema>;
export type ObservationDistilledFeatures = z.infer<typeof observationDistilledFeaturesSchema>;
export type ObservationScoreSnapshot = z.infer<typeof observationScoreSnapshotSchema>;
export type ObservationProvenance = z.infer<typeof observationProvenanceSchema>;
export type BrowserObservationRecord = z.infer<typeof browserObservationRecordSchema>;
export type ManualReportIssueType = z.infer<typeof manualReportIssueTypeSchema>;
export type VerificationStatus = z.infer<typeof verificationStatusSchema>;
export type VerificationTrigger = z.infer<typeof verificationTriggerSchema>;
export type VerificationProvenance = z.infer<typeof verificationProvenanceSchema>;
export type ActionDecisionBasis = z.infer<typeof actionDecisionBasisSchema>;
export type ArtifactProvenance = z.infer<typeof artifactProvenanceSchema>;
export type LabelCandidateFeedbackSummary = z.infer<typeof labelCandidateFeedbackSummarySchema>;
export type LabelCandidateSplitSafety = z.infer<typeof labelCandidateSplitSafetySchema>;
export type LabelCandidateProvenance = z.infer<typeof labelCandidateProvenanceSchema>;
export type LabelCandidateQueue = z.infer<typeof labelCandidateQueueSchema>;
export type LabelCandidate = z.infer<typeof labelCandidateSchema>;
export type ManualReportWorkflowMode = z.infer<
  typeof manualReportWorkflowModeSchema
>;
export type ManualReportRequestedOutcome = z.infer<
  typeof manualReportRequestedOutcomeSchema
>;
export type ManualReportIssue = z.infer<typeof manualReportIssueSchema>;
export type ManualReport = z.infer<typeof manualReportSchema>;
export type ManualReportOptimizationRequest = z.infer<
  typeof manualReportOptimizationRequestSchema
>;
export type ManualReportOptimizationResponse = z.infer<
  typeof manualReportOptimizationResponseSchema
>;
export type ManualReportSuggestionIssue = z.infer<
  typeof manualReportSuggestionIssueSchema
>;
export type ManualReportSuggestionRequest = z.infer<
  typeof manualReportSuggestionRequestSchema
>;
export type ManualReportSuggestionResponse = z.infer<
  typeof manualReportSuggestionResponseSchema
>;
export type ReviewPromptState = z.infer<typeof reviewPromptStateSchema>;
export type ReviewStatusEvent = z.infer<typeof reviewStatusEventSchema>;
export type ExplanationBundlePayload = z.infer<
  typeof explanationBundlePayloadSchema
>;
export type MobileResolvedWatchContext = z.infer<
  typeof mobileResolvedWatchContextSchema
>;
export type MobileAnalyzeShareRequest = z.infer<
  typeof mobileAnalyzeShareRequestSchema
>;
export type MobileAnalyzeShareResponse = z.infer<
  typeof mobileAnalyzeShareResponseSchema
>;
export type YouTubeAuthStatus = z.infer<typeof youtubeAuthStatusSchema>;
export type YouTubeReportRequest = z.infer<typeof youtubeReportRequestSchema>;
export type YouTubeReportResponse = z.infer<typeof youtubeReportResponseSchema>;
