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

export function createBootstrapScore(item: ScoreItemRequest): ScoreResult {
  const title = item.title.toLowerCase();
  const hits = suspiciousTokens.filter((token) => title.includes(token)).length;
  const channelMuted = item.user_context.muted_channels.some(
    (channel) => channel.trim().toLowerCase() === item.channel.channel_name.trim().toLowerCase(),
  );
  const transcriptMismatch =
    item.transcript_excerpt && !item.transcript_excerpt.toLowerCase().includes(title.split(' ')[0] || '')
      ? 0.12
      : 0;
  const strictBias = item.user_context.strict_mode ? 0.05 : 0;
  const risk = channelMuted
    ? 0.99
    : Math.min(0.15 + hits * 0.17 + item.channel.prior_flags * 0.03 + strictBias + transcriptMismatch, 0.98);
  const confidence = Math.min(0.55 + hits * 0.1, 0.95);
  const recommendedAction =
    risk < 0.35 ? 'none' : risk < 0.6 ? 'badge' : risk < 0.8 ? 'blur' : risk < 0.93 ? 'ask-report' : 'hide';
  const reasons: string[] = [];

  if (channelMuted) {
    reasons.push('Channel is locally muted in this browser profile.');
  }
  if (hits > 0) {
    reasons.push('Title contains sensational framing patterns.');
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
