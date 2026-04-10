import { describe, expect, it } from 'vitest';

import {
  datasetRecordSchema,
  manualReportSchema,
  manualReportSuggestionRequestSchema,
  scoreItemRequestSchema,
  scoreResultSchema,
} from './index';

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
      fused_score: 0.76,
      calibrated_score: 0.74,
      confidence: 0.9,
      uncertainty: 0.1,
      uncertainty_bucket: 'low',
      path_scores: { text: 0.81, vision: 0.64, fusion: 0.76, calibration: 0.74 },
      path_contributors: { text: ['breaking', 'confirmed'] },
      content_class: 'news',
      content_class_confidence: 0.88,
      bias_profile: {
        metrics: { sensational_weight: 0.72 },
        positive_biases: ['factual-scrutiny'],
        negative_biases: ['sensational-overweighting'],
        guardrail_applied: 'factual-context-amplifies-mismatch',
      },
      verification: {
        status: 'completed',
        triggers: ['high-risk', 'threshold-near'],
        reasons: ['Selective verification confirmed elevated packaging mismatch.'],
        summary: 'Selective verification confirmed elevated packaging mismatch.',
        review_recommended: true,
      },
      action_decision_basis: {
        threshold_action: 'blur',
        final_action: 'blur',
        decisive_layer: 'threshold',
        verification_considered: true,
        policy_reason: 'Selective verification confirmed elevated packaging mismatch.',
      },
      policy_mode: 'bseo-shadow',
      resolved_policy_mode: 'bseo-shadow',
      artifact_provenance: {
        model_version: 'baseline-v1-build-test',
        model_build_id: 'build-test',
        policy_version: 'bseo-control-policy-v1-shadow',
        policy_build_id: 'build-bseo',
        policy_artifact_status: 'compatible',
      },
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
        {
          kind: 'verification',
          label: 'Selective deep verification completed',
          score: 0.74,
          details: 'Selective verification confirmed elevated packaging mismatch.',
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

  it('accepts taxonomy-aware manual report suggestion requests', () => {
    const result = manualReportSuggestionRequestSchema.safeParse({
      target_url: 'https://www.youtube.com/watch?v=123',
      title_snapshot: 'Moonlight Echoes (Official Audio)',
      channel_name: 'Aurora Records',
      explanation_summary: 'Packaging appears broadly aligned.',
      reasons: ['Class-conditioned guardrail reduced the mismatch penalty.'],
      content_class: 'music',
      content_class_confidence: 0.92,
      bias_profile: {
        metrics: { crossmodal_rigidity: 0.28 },
        positive_biases: ['stylistic-divergence-tolerance'],
        negative_biases: [],
        guardrail_applied: 'music-context-dampens-crossmodal-rigidity',
      },
    });

    expect(result.success).toBe(true);
  });

  it('accepts manual review tags and collection provenance on manual reports', () => {
    const result = manualReportSchema.safeParse({
      workflow_mode: 'report',
      target_url: 'https://www.youtube.com/watch?v=123&list=RD123',
      title_snapshot: 'Secret lab leak footage',
      transcript_excerpt: null,
      issues: [{ issue_type: 'title', comment: 'The title overstates certainty.' }],
      requested_outcome: 'moderate',
      selected_tags: ['Clickbait'],
      suggested_tags: [
        {
          tag: 'Clickbait',
          selected: true,
          confidence: 0.92,
          rationale: 'Report mode defaults to Clickbait.',
        },
      ],
      collection_scope: {
        scope_type: 'mix',
        scope_id: 'RD123',
        collection_title: 'Signal Watch Mix',
        source_item_id: '123',
        source_link_url: 'https://www.youtube.com/watch?v=123&list=RD123',
        trigger_origin: 'collection-preview',
        apply_to_all: true,
        resolved_member_count: 2,
        unresolved_member_count: 1,
        member_items: [
          {
            item_id: '123',
            title_snapshot: 'Secret lab leak footage',
            channel_name: 'Signal Watch',
            link_url: 'https://www.youtube.com/watch?v=123&list=RD123',
            thumbnail_ref: 'https://img.youtube.com/vi/123/default.jpg',
            resolved: true,
          },
        ],
      },
      optimize_requested: false,
      optimize_applied: false,
      report_text: 'Please review the misleading packaging.',
    });

    expect(result.success).toBe(true);
  });

  it('adds runtime context defaults to score requests', () => {
    const result = scoreItemRequestSchema.parse({
      item_id: 'item-1',
      title: 'Breaking aliens confirmed',
      metadata: {},
      channel: { channel_name: 'TruthLens Test' },
    });

    expect(result.runtime_context.surface).toBe('unknown');
    expect(result.runtime_context.review_requested).toBe(false);
  });
});
