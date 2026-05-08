// @vitest-environment jsdom
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  fetchFeedbackSummary: vi.fn(async () => ({
    total_events: 0,
    correction_rate: 0,
    top_channels: [],
  })),
  fetchModelInfo: vi.fn(async () => ({
    mode: 'hosted-beta',
    model_version: 'test',
    artifact_status: 'ok',
    architecture_plan_version: 'test',
    available_heads: [],
    head_specs: [],
    architecture_layers: [],
    text_encoder_resolution: null,
    vision_encoder_resolution: null,
    history_encoder_resolution: null,
  })),
  fetchPolicyInfo: vi.fn(async () => ({
    policy_version: 'test',
    policy_mode: 'test',
    resolved_policy_mode: 'test',
    effective_thresholds: {},
    bseo_artifact: { available: true, compatible: true, stale: false, policy_version: 'test' },
  })),
}));

const sessionMocks = vi.hoisted(() => ({
  loadExtensionSessionStats: vi.fn(async () => ({
    itemCount: 0,
    flaggedCount: 0,
    lastScore: null,
    updatedAt: null,
  })),
}));

const rerankSettingMocks = vi.hoisted(() => ({
  DEFAULT_FEED_RERANK_ENABLED: false,
  loadFeedRerankEnabled: vi.fn(async () => false),
  persistFeedRerankEnabled: vi.fn(async (enabled: boolean) => {
    void enabled;
  }),
}));

vi.mock('./lib/api', () => apiMocks);
vi.mock('./lib/sessionStats', () => sessionMocks);
vi.mock('./lib/feedRerankSettings', () => rerankSettingMocks);

import { Popup } from './popup';

async function flushUi() {
  for (let index = 0; index < 3; index += 1) {
    await Promise.resolve();
    await new Promise((resolve) => window.setTimeout(resolve, 0));
  }
}

function getRerankToggle(): HTMLInputElement {
  const input = document.querySelector<HTMLInputElement>('input[type="checkbox"]');
  if (!input) {
    throw new Error('Could not find rerank checkbox input');
  }
  return input;
}

describe('popup rerank setting', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    vi.clearAllMocks();
    root.unmount();
    container.remove();
  });

  it('renders reranking as off by default when storage is missing', async () => {
    root.render(<Popup />);
    await flushUi();

    const checkbox = getRerankToggle();
    expect(checkbox.checked).toBe(false);

    await flushUi();
    expect(rerankSettingMocks.loadFeedRerankEnabled).toHaveBeenCalled();
    expect(getRerankToggle().checked).toBe(false);
  });

  it('persists the user toggle changes', async () => {
    root.render(<Popup />);
    await flushUi();

    const checkbox = getRerankToggle();
    checkbox.click();
    await flushUi();

    expect(rerankSettingMocks.persistFeedRerankEnabled).toHaveBeenCalledWith(true);

    checkbox.click();
    await flushUi();

    expect(rerankSettingMocks.persistFeedRerankEnabled).toHaveBeenCalledWith(false);
  });
});
