import type { ScoreItemRequest, ScoreResult } from '@truthlens/shared-schemas';
import { scoreResultSchema } from '@truthlens/shared-schemas';

const suspiciousTokens = [
  'breaking',
  'shocking',
  'confirmed',
  'secret',
  'aliens',
  'urgent',
  'exposed',
];

const curiosityTokens = [
  'stay out',
  "shouldn't",
  'shouldnt',
  'hidden',
  'warning',
  'banned',
  'do not enter',
  'you wont believe',
  "you won't believe",
];

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function keywordSet(value: string): Set<string> {
  return new Set(
    value
      .toLowerCase()
      .match(/[a-z0-9']+/g)
      ?.filter((token) => token.length >= 4) ?? [],
  );
}

function inferContentClass(item: ScoreItemRequest): string {
  const text = `${item.title} ${item.description_snapshot ?? ''} ${item.transcript_excerpt ?? ''} ${item.channel.channel_name}`.toLowerCase();
  if (
    /(official audio|music video|lyric video|chorus|verse|album|single|records|beat|beats|type beat|instrumental|song|track|lofi|lo-fi|mix|soundtrack|artist|prod\.|produced by)/.test(
      text,
    )
  ) {
    return 'music';
  }
  if (/(documentary|explainer|investigation|history|lecture|lesson|course|case study)/.test(text)) {
    return 'documentary';
  }
  if (/(analysis|reaction|opinion|debate|review|comparison|tutorial|how to|how-to|hands on|hands-on)/.test(text)) {
    return 'commentary';
  }
  if (/(trailer|promo|teaser|sale|discount|official trailer|reveal trailer|sponsored)/.test(text)) {
    return 'promo';
  }
  if (/(parody|satire|spoof|meme)/.test(text)) {
    return 'satire';
  }
  if (/(gameplay|walkthrough|speedrun|gaming)/.test(text)) {
    return 'gaming';
  }
  if (
    /(gallery|art|painting|illustration|artwork|cover art|concept art|digital art|drawing|sketch|sketchbook|exhibition|studio|artist|creator|portfolio)/.test(
      text,
    )
  ) {
    return 'art';
  }
  if (/(breaking|news|officials|alert|report|transfer|injury)/.test(text)) {
    return 'news';
  }
  return 'unknown';
}

function createSemanticEvidenceRoute(
  item: ScoreItemRequest,
  contentClass: string,
  contentClassConfidence: number,
) {
  const text = `${item.title} ${item.description_snapshot ?? ''}`.toLowerCase();
  const history = item.channel.channel_history_features;
  const negativeChannelHistory =
    item.channel.prior_flags > 0 ||
    Number(history.channel_risk_mean ?? 0) >= 0.55 ||
    Number(history.repeat_template_rate ?? 0) >= 0.45 ||
    Number(history.trust_score ?? 5) <= 4;
  const fakeOfficialClaim =
    /(official (government|warning|report|leak|proof)|government confirms|government confirmed|police confirmed|court confirmed|who confirms|cdc confirms|breaking|confirmed|bank|finance|election|health|vaccine|crisis)/.test(
      text,
    );
  const scammyDescription =
    /(claim now|free prize|free reward|guaranteed profit|double your money|crypto giveaway|telegram|whatsapp|cashapp)/.test(
      item.description_snapshot?.toLowerCase() ?? '',
    );
  const creative = contentClass === 'music' || contentClass === 'art';
  const preservedLearningEvidence = [
    'title',
    'description_snapshot',
    'transcript_excerpt',
    'thumbnail_ref',
    'thumbnail_features',
    'channel',
    'metadata',
    'score',
    'content_class',
    'route',
    'class_confidence',
    'adversarial_guard',
    'feedback',
    'verify_report_outcome',
    'user_correction',
    'later_adjudication_state',
  ];

  if (
    creative &&
    contentClassConfidence >= 0.62 &&
    !negativeChannelHistory &&
    !fakeOfficialClaim &&
    !scammyDescription
  ) {
    return {
      content_class: contentClass,
      class_confidence: Number(contentClassConfidence.toFixed(2)),
      runtime_route: 'minimal_creative',
      learning_capture_plan: 'full_multimodal_capture',
      adversarial_guard: 'clean',
      mismatch_pressure: 'reduced',
      required_runtime_evidence: ['title', 'channel_sanity', 'light_spam_check'],
      preserved_learning_evidence: preservedLearningEvidence,
      route_reasons: [
        'Title or taxonomy indicates creative music/art context.',
        'No suspicious factual claim detected.',
      ],
    };
  }

  if (creative && (negativeChannelHistory || fakeOfficialClaim || scammyDescription)) {
    return {
      content_class: contentClass,
      class_confidence: Number(contentClassConfidence.toFixed(2)),
      runtime_route: 'ambiguous_escalated',
      learning_capture_plan: 'full_multimodal_capture',
      adversarial_guard: 'triggered',
      mismatch_pressure: 'normal',
      required_runtime_evidence: ['title', 'description', 'thumbnail', 'channel_history', 'light_spam_check'],
      preserved_learning_evidence: preservedLearningEvidence,
      route_reasons: ['Creative-looking context requires adversarial guard escalation.'],
    };
  }

  if (contentClass === 'news' || fakeOfficialClaim) {
    return {
      content_class: contentClass,
      class_confidence: Number(contentClassConfidence.toFixed(2)),
      runtime_route: 'high_risk_factual',
      learning_capture_plan: 'full_multimodal_capture',
      adversarial_guard: fakeOfficialClaim ? 'triggered' : 'clean',
      mismatch_pressure: 'elevated',
      required_runtime_evidence: [
        'title',
        'description',
        'thumbnail',
        'channel_history',
        'light_spam_check',
        'factual_claim_guard',
      ],
      preserved_learning_evidence: preservedLearningEvidence,
      route_reasons: ['Factual or high-risk claim context requires strong consistency analysis.'],
    };
  }

  if (contentClass === 'commentary' || contentClass === 'documentary') {
    return {
      content_class: contentClass,
      class_confidence: Number(contentClassConfidence.toFixed(2)),
      runtime_route: 'informational_consistency',
      learning_capture_plan: 'full_multimodal_capture',
      adversarial_guard: 'clean',
      mismatch_pressure: 'normal',
      required_runtime_evidence: ['title', 'description', 'thumbnail', 'channel_context', 'light_spam_check'],
      preserved_learning_evidence: preservedLearningEvidence,
      route_reasons: ['Informational content expects cross-signal consistency.'],
    };
  }

  return {
    content_class: contentClass,
    class_confidence: Number(contentClassConfidence.toFixed(2)),
    runtime_route: 'ambiguous_escalated',
    learning_capture_plan: 'full_multimodal_capture',
    adversarial_guard: 'triggered',
    mismatch_pressure: 'normal',
    required_runtime_evidence: ['title', 'description', 'thumbnail', 'channel_history', 'light_spam_check'],
    preserved_learning_evidence: preservedLearningEvidence,
    route_reasons: ['Available signals are insufficient for a light route.'],
  };
}

export function createBootstrapScore(item: ScoreItemRequest): ScoreResult {
  const title = item.title.toLowerCase();
  const hits = suspiciousTokens.filter((token) => title.includes(token)).length;
  const curiosityHits = curiosityTokens.filter((token) => title.includes(token)).length;
  const uppercaseLetters = item.title.replace(/[^A-Z]/g, '').length;
  const alphaLetters = item.title.replace(/[^A-Za-z]/g, '').length;
  const uppercaseRatio = alphaLetters > 0 ? uppercaseLetters / alphaLetters : 0;
  const punctuationIntensity = (item.title.match(/[!?]/g) ?? []).length;
  const titleTokenCount = item.title.split(/\s+/).filter(Boolean).length;
  const titleKeywords = keywordSet(item.title);
  const transcriptKeywords = keywordSet(item.transcript_excerpt ?? '');
  const overlap =
    titleKeywords.size > 0 && transcriptKeywords.size > 0
      ? [...titleKeywords].filter((token) => transcriptKeywords.has(token)).length /
        Math.min(titleKeywords.size, transcriptKeywords.size)
      : 0;
  const channelMuted = item.user_context.muted_channels.some(
    (channel) => channel.trim().toLowerCase() === item.channel.channel_name.trim().toLowerCase(),
  );
  const transcriptMismatch =
    item.transcript_excerpt && overlap < 0.18
      ? clamp(0.08 + (0.18 - overlap) * 0.5, 0.08, 0.18)
      : 0;
  const contentClass = inferContentClass(item);
  const contentClassConfidence = contentClass === 'unknown' ? 0.32 : 0.72;
  const semanticEvidenceRoute = createSemanticEvidenceRoute(
    item,
    contentClass,
    contentClassConfidence,
  );
  const strictBias = item.user_context.strict_mode ? 0.05 : 0;
  const viewCountLog = Math.log10((item.metadata.view_count ?? 0) + 1);
  const durationFactor = clamp((item.metadata.duration_seconds ?? 0) / 1800, 0, 1);
  const titleLengthFactor = clamp(titleTokenCount / 14, 0, 1);
  const risk = channelMuted
    ? 0.99
    : Math.min(
        0.08 +
          hits * 0.15 +
          curiosityHits * 0.11 +
          item.channel.prior_flags * 0.03 +
          uppercaseRatio * 0.16 +
          Math.min(punctuationIntensity, 3) * 0.03 +
          titleLengthFactor * 0.04 +
          durationFactor * 0.03 +
          Math.min(viewCountLog, 6) * 0.01 +
          strictBias +
          transcriptMismatch,
        0.98,
      );
  const confidence = Math.min(
    0.5 + hits * 0.08 + curiosityHits * 0.07 + uppercaseRatio * 0.1 + transcriptMismatch * 0.6,
    0.95,
  );
  const recommendedAction =
    risk < 0.35 ? 'none' : risk < 0.6 ? 'badge' : risk < 0.8 ? 'blur' : risk < 0.93 ? 'ask-report' : 'hide';
  const reasons: string[] = [];

  if (channelMuted) {
    reasons.push('Channel is locally muted in this browser profile.');
  }
  if (hits > 0) {
    reasons.push('Title contains sensational framing patterns.');
  }
  if (curiosityHits > 0) {
    reasons.push('Title contains warning-style or curiosity-driven framing patterns.');
  }
  if (item.channel.prior_flags > 0) {
    reasons.push('Channel history contributes additional risk context.');
  }
  if (transcriptMismatch > 0) {
    reasons.push('Title and transcript excerpt appear weakly aligned.');
  }
  if (recommendedAction === 'ask-report') {
    reasons.push('Risk crossed the high-risk prompt threshold.');
  }
  if (recommendedAction === 'hide') {
    reasons.push('Risk crossed the local hide threshold.');
  }

  const explanationId = `exp-${item.item_id.replace(/[^a-z0-9_-]/gi, '-').toLowerCase()}`;
  const explanationSummary =
    reasons.length > 0
      ? reasons.slice(0, 2).join(' ')
      : 'No active intervention is recommended for this item.';
  const evidence = reasons.map((reason, index) => ({
    kind:
      index === 0 && channelMuted
        ? 'user-context'
        : reason.toLowerCase().includes('transcript')
          ? 'transcript'
          : reason.toLowerCase().includes('channel')
            ? 'history'
            : reason.toLowerCase().includes('hide') || reason.toLowerCase().includes('threshold')
              ? 'policy'
            : 'title',
    label: reason.replace(/\.$/, ''),
    score: Number(risk.toFixed(2)),
    details: reason,
  }));
  evidence.unshift({
    kind: 'taxonomy',
    label: `Content class detected: ${contentClass}`,
    score: Number(contentClassConfidence.toFixed(2)),
    details: `Bootstrap taxonomy inferred '${contentClass}' content for this item.`,
  });
  if (transcriptMismatch > 0 || item.channel.prior_flags > 0) {
    evidence.push({
      kind: 'bias',
      label: 'Negative bias signal triggered intervention',
      score: Number(risk.toFixed(2)),
      details:
        transcriptMismatch > 0
          ? 'Negative bias triggered: crossmodal-overreach.'
          : 'Negative bias triggered: channel-lock-in-risk.',
    });
  }

  return scoreResultSchema.parse({
    risk_score: Number(risk.toFixed(2)),
    confidence: Number(confidence.toFixed(2)),
    uncertainty: Number((1 - confidence).toFixed(2)),
    content_class: contentClass,
    content_class_confidence: Number(contentClassConfidence.toFixed(2)),
    semantic_evidence_route: semanticEvidenceRoute,
    bias_profile: {
      metrics: {
        sensational_weight: Number(Math.min(1, hits * 0.2 + curiosityHits * 0.14).toFixed(2)),
        crossmodal_rigidity: Number(transcriptMismatch.toFixed(2)),
        channel_prior_dependency: Number(Math.min(1, item.channel.prior_flags * 0.18).toFixed(2)),
        genre_confusion: Number((contentClass === 'unknown' ? 0.62 : 0.22).toFixed(2)),
        uncertainty_calibration: Number(Math.abs((1 - confidence) - 0.22).toFixed(2)),
      },
      positive_biases:
        contentClass === 'music' || contentClass === 'art'
          ? ['stylistic-divergence-tolerance']
          : ['factual-scrutiny'],
      negative_biases:
        transcriptMismatch > 0
          ? ['crossmodal-overreach']
          : item.channel.prior_flags > 0
            ? ['channel-lock-in-risk']
            : [],
      guardrail_applied:
        contentClass === 'music'
          ? 'music-context-dampens-crossmodal-rigidity'
          : contentClass === 'art'
            ? 'art-context-preserves-stylistic-divergence'
            : 'unknown-context-uses-balanced-guardrail',
    },
    recommended_action: recommendedAction,
    reasons,
    explanation_id: recommendedAction === 'none' ? null : explanationId,
    explanation_summary: recommendedAction === 'none' ? null : explanationSummary,
    evidence,
  });
}
