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
  const risk = Math.min(0.15 + hits * 0.17 + item.channel.prior_flags * 0.03, 0.98);
  const confidence = Math.min(0.55 + hits * 0.1, 0.95);
  const recommendedAction =
    risk < 0.35 ? 'none' : risk < 0.6 ? 'badge' : risk < 0.8 ? 'blur' : 'ask-report';
  const reasons: string[] = [];

  if (hits > 0) {
    reasons.push('Title contains sensational framing patterns.');
  }
  if (item.channel.prior_flags > 0) {
    reasons.push('Channel history contributes additional risk context.');
  }
  if (recommendedAction === 'ask-report') {
    reasons.push('Risk crossed the high-risk prompt threshold.');
  }

  return scoreResultSchema.parse({
    risk_score: Number(risk.toFixed(2)),
    confidence: Number(confidence.toFixed(2)),
    uncertainty: Number((1 - confidence).toFixed(2)),
    recommended_action: recommendedAction,
    reasons,
  });
}
