import { describe, expect, it } from 'vitest';

import { annotationBatchSchema } from './annotationBatch';

describe('annotationBatchSchema', () => {
  it('parses annotation batch payloads', () => {
    const provenance = {
      generated_at: '2026-03-23T00:00:00Z',
      generator: 'browser-feedback-intake-v1',
      candidate_sources: ['pipeline-batch'],
      observation_ids: [],
      feedback_event_ids: [],
      source_paths: ['datasets/labels/annotation_batches/run-1.json'],
    };

    const result = annotationBatchSchema.parse({
      run_id: 'run-1',
      generated_at: '2026-03-23T00:00:00Z',
      review_queue: [
        {
          candidate_id: 'candidate-1',
          item_id: 'item-1',
          queue_name: 'review',
          origin: 'pipeline-batch',
          title: 'Flag this',
          channel_name: 'Channel One',
          weak_label_score: 0.88,
          content_class: 'news',
          dominant_bias_risk: 'channel_prior_dependency',
          current_labels: { clickbait: true },
          annotator_notes: ['needs adjudication'],
          queue_reason: 'Needs review',
          feedback_summary: {
            total_events: 1,
            risk_event_count: 1,
            benign_event_count: 0,
            manual_report_count: 0,
            last_user_action: 'flag',
          },
          provenance,
          split_safety: {
            dataset_membership: 'existing-batch',
            split_status: 'assigned',
            split_name: 'validation',
            dataset_build_id: 'build-1',
            annotation_run_id: 'run-1',
            eligible_for_training: false,
            leakage_guard_reason: null,
          },
        },
      ],
      hard_negative_queue: [
        {
          candidate_id: 'candidate-2',
          item_id: 'item-2',
          queue_name: 'hard-negative',
          origin: 'supplemental-intake',
          title: 'Do not flag',
          current_labels: { clickbait: false },
          annotator_notes: [],
          feedback_summary: {
            total_events: 1,
            risk_event_count: 0,
            benign_event_count: 1,
            manual_report_count: 0,
            last_user_action: 'dismiss',
          },
          provenance: {
            ...provenance,
            candidate_sources: ['feedback-event'],
          },
          split_safety: {
            dataset_membership: 'supplemental-intake',
            split_status: 'blocked-until-ingestion',
            split_name: 'unknown',
            dataset_build_id: null,
            annotation_run_id: 'run-1',
            eligible_for_training: false,
            leakage_guard_reason: 'Supplemental intake must be adjudicated before split assignment.',
          },
        },
      ],
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
    expect(result.review_queue[0].provenance.generator).toBe('browser-feedback-intake-v1');
    expect(result.hard_negative_queue[0].split_safety.split_status).toBe('blocked-until-ingestion');
    expect(result.class_coverage.news).toBe(1);
    expect(result.adjudication_summary?.saved_count).toBe(1);
  });
});
