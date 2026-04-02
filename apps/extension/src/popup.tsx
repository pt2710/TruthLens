import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

import {
  fetchFeedbackSummary,
  fetchModelInfo,
  fetchPolicyInfo,
  type FeedbackSummary,
  type ModelInfo,
  type PolicyInfo,
} from './lib/api';
import {
  loadExtensionSessionStats,
  type ExtensionSessionStats,
} from './lib/sessionStats';

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'grid', gap: 2 }}>
      <strong>{value}</strong>
      <span style={{ color: '#555', fontSize: 12 }}>{label}</span>
    </div>
  );
}

function Popup() {
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [policyInfo, setPolicyInfo] = useState<PolicyInfo | null>(null);
  const [feedbackSummary, setFeedbackSummary] =
    useState<FeedbackSummary | null>(null);
  const [sessionStats, setSessionStats] =
    useState<ExtensionSessionStats | null>(null);

  useEffect(() => {
    Promise.all([
      fetchModelInfo(),
      fetchPolicyInfo(),
      fetchFeedbackSummary(),
      loadExtensionSessionStats(),
    ]).then(
      ([
        nextModelInfo,
        nextPolicyInfo,
        nextFeedbackSummary,
        nextSessionStats,
      ]) => {
        setModelInfo(nextModelInfo);
        setPolicyInfo(nextPolicyInfo);
        setFeedbackSummary(nextFeedbackSummary);
        setSessionStats(nextSessionStats);
      },
    );
  }, []);

  const architectureLayers = modelInfo?.architecture_layers ?? [];
  const implementedLayerCount = architectureLayers.filter(
    (layer) => layer.status === 'implemented',
  ).length;
  const plannedLayerCount = architectureLayers.filter(
    (layer) => layer.status === 'planned',
  ).length;
  const textEncoderResolution = modelInfo?.text_encoder_resolution;

  return (
    <main
      style={{
        fontFamily: 'Segoe UI, sans-serif',
        padding: 16,
        width: 320,
        display: 'grid',
        gap: 14,
      }}
    >
      <section style={{ display: 'grid', gap: 6 }}>
        <h1 style={{ margin: 0 }}>TruthLens</h1>
        <p style={{ margin: 0, color: '#555' }}>
          Live policy, model, and feedback state for the current local setup.
        </p>
      </section>

      <section style={{ display: 'grid', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Current Session</h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 8,
          }}
        >
          <Metric
            label="Scanned items"
            value={String(sessionStats?.itemCount ?? 0)}
          />
          <Metric
            label="Flagged items"
            value={String(sessionStats?.flaggedCount ?? 0)}
          />
        </div>
        {sessionStats?.lastScore ? (
          <div
            style={{
              display: 'grid',
              gap: 4,
              padding: 8,
              borderRadius: 8,
              background: '#f4f5f7',
            }}
          >
            <strong>Latest decision</strong>
            <span style={{ color: '#555', fontSize: 12 }}>
              risk {sessionStats.lastScore.risk_score.toFixed(2)} | action{' '}
              {sessionStats.lastScore.recommended_action}
            </span>
            {sessionStats.lastScore.explanation_summary ? (
              <span style={{ color: '#555', fontSize: 12 }}>
                Why: {sessionStats.lastScore.explanation_summary}
              </span>
            ) : null}
          </div>
        ) : (
          <p style={{ margin: 0, color: '#555', fontSize: 12 }}>
            No active YouTube session statistics recorded yet.
          </p>
        )}
      </section>

      <section style={{ display: 'grid', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Model</h2>
        <div style={{ display: 'grid', gap: 6 }}>
          <Metric label="Mode" value={modelInfo?.mode ?? 'loading'} />
          <Metric
            label="Version"
            value={modelInfo?.model_version ?? 'loading'}
          />
          <Metric
            label="Artifacts"
            value={modelInfo?.artifact_status ?? 'loading'}
          />
          <Metric
            label="Architecture plan"
            value={modelInfo?.architecture_plan_version ?? 'loading'}
          />
          <p style={{ margin: 0, color: '#555', fontSize: 12 }}>
            Heads:{' '}
            {(modelInfo?.available_heads ?? []).join(', ') ||
              'bootstrap-fallback'}
          </p>
          <div style={{ display: 'grid', gap: 4 }}>
            {(modelInfo?.head_specs ?? []).slice(0, 6).map((head) => (
              <span key={head.name} style={{ color: '#555', fontSize: 12 }}>
                {head.name}: {head.family} via {head.backend}
              </span>
            ))}
          </div>
          <div
            style={{
              display: 'grid',
              gap: 4,
              padding: 8,
              borderRadius: 8,
              background: '#f4f5f7',
            }}
          >
            <strong>Architecture Layers</strong>
            <span style={{ color: '#555', fontSize: 12 }}>
              implemented {implementedLayerCount} | planned {plannedLayerCount}
            </span>
            {architectureLayers.slice(0, 5).map((layer) => (
              <span
                key={layer.component_id}
                style={{ color: '#555', fontSize: 12 }}
              >
                {layer.label}: {layer.layer_type} via {layer.backend}
              </span>
            ))}
            {textEncoderResolution ? (
              <span style={{ color: '#555', fontSize: 12 }}>
                text encoder {textEncoderResolution.actual_encoder}
                {textEncoderResolution.fallback_used
                  ? ` (fallback from ${textEncoderResolution.requested_encoder})`
                  : textEncoderResolution.requested_encoder !==
                      textEncoderResolution.actual_encoder
                    ? ` (requested ${textEncoderResolution.requested_encoder})`
                    : ''}
              </span>
            ) : null}
          </div>
        </div>
      </section>

      <section style={{ display: 'grid', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Thresholds</h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 8,
          }}
        >
          {Object.entries(policyInfo?.effective_thresholds ?? {}).map(
            ([label, value]) => (
              <Metric key={label} label={label} value={value.toFixed(2)} />
            ),
          )}
        </div>
      </section>

      <section style={{ display: 'grid', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Feedback Loop</h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 8,
          }}
        >
          <Metric
            label="Events"
            value={String(feedbackSummary?.total_events ?? 0)}
          />
          <Metric
            label="Correction rate"
            value={
              ((feedbackSummary?.correction_rate ?? 0) * 100).toFixed(0) + '%'
            }
          />
        </div>
        <div style={{ display: 'grid', gap: 6 }}>
          {(feedbackSummary?.top_channels ?? []).length === 0 ? (
            <p style={{ margin: 0, color: '#555', fontSize: 12 }}>
              No channel-specific feedback recorded yet.
            </p>
          ) : (
            feedbackSummary?.top_channels.map((channel) => (
              <div
                key={channel.channel_name}
                style={{
                  display: 'grid',
                  gap: 2,
                  padding: 8,
                  borderRadius: 8,
                  background: '#f4f5f7',
                }}
              >
                <strong>{channel.channel_name}</strong>
                <span style={{ color: '#555', fontSize: 12 }}>
                  bias {channel.bias.toFixed(2)} | events {channel.event_count}{' '}
                  | reports {channel.report_count} | dismissals{' '}
                  {channel.dismiss_count}
                </span>
              </div>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<Popup />);
}
