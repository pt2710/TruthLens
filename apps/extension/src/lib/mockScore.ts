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

export function createBootstrapScore(item: ScoreItemRequest): ScoreResult {
  const title = item.title.toLowerCase();
  const hits = suspiciousTokens.filter((token) => title.includes(token)).length;
  const curiosityHits = curiosityTokens.filter((token) => title.includes(token)).length;
  const uppercaseLetters = item.title.replace(/[^A-Z]/g, '').length;
  const alphaLetters = item.title.replace(/[^A-Za-z]/g, '').length;
  const uppercaseRatio = alphaLetters > 0 ? uppercaseLetters / alphaLetters : 0;
  const punctuationIntensity = (item.title.match(/[!?]/g) ?? []).length;
  const titleTokenCount = item.title.split(/\s+/).filter(Boolean).length;
  const transcriptText = item.transcript_excerpt?.toLowerCase() ?? '';
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

  return scoreResultSchema.parse({
    risk_score: Number(risk.toFixed(2)),
    confidence: Number(confidence.toFixed(2)),
    uncertainty: Number((1 - confidence).toFixed(2)),
    recommended_action: recommendedAction,
    reasons,
    explanation_id: recommendedAction === 'none' ? null : explanationId,
    explanation_summary: recommendedAction === 'none' ? null : explanationSummary,
    evidence,
  });
}
