import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  HOSTED_BETA_API_BASE,
  buildTruthLensApiUrl,
  resolveTruthLensApiBase,
} from './runtimeConfig';

describe('runtimeConfig', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('uses the committed hosted beta API base as the production default', () => {
    expect(HOSTED_BETA_API_BASE).toBe('https://truthlens-beta-api.onrender.com');
  });

  it('prefers an explicit VITE_TRUTHLENS_API_BASE override when present', () => {
    vi.stubEnv('VITE_TRUTHLENS_API_BASE', 'https://example.com///');

    expect(resolveTruthLensApiBase()).toBe('https://example.com');
    expect(buildTruthLensApiUrl('/manual-report/suggest')).toBe(
      'https://example.com/manual-report/suggest',
    );
  });
});
