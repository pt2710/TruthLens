import { useEffect, useState } from 'react';

import {
  type AnnotationBatch,
  type AnnotationDecision,
  type AnnotationQueueName,
  type AnnotationResolution,
  type QueueEntry,
  loadAnnotationBatch,
  saveAnnotationAdjudications,
} from './lib/annotationBatch';
import './styles.css';

const CONTENT_CLASS_OPTIONS = [
  'news',
  'commentary',
  'documentary',
  'music',
  'art',
  'satire',
  'gaming',
  'promo',
  'unknown',
] as const;

const EDITABLE_LABEL_KEYS = [
  'clickbait',
  'misleading_thumbnail',
  'misleading_title',
  'fearbait',
  'ai_mass_spam',
  'deceptive_divergence',
  'stylistic_divergence',
] as const;

const RESOLUTION_OPTIONS: Array<{ value: '' | AnnotationResolution; label: string }> = [
  { value: '', label: 'Pending' },
  { value: 'confirmed-risk', label: 'Confirmed risk' },
  { value: 'confirmed-benign', label: 'Confirmed benign' },
  { value: 'needs-escalation', label: 'Needs escalation' },
];

type DecisionDraft = {
  itemId: string;
  queueName: AnnotationQueueName;
  resolution: '' | AnnotationResolution;
  contentClass: string;
  biasReviewRequired: boolean;
  labelOverrides: Record<string, boolean>;
  note: string;
};

function buildDecisionDraft(item: QueueEntry, queueName: AnnotationQueueName): DecisionDraft {
  return {
    itemId: item.item_id,
    queueName,
    resolution: item.adjudication?.resolution ?? '',
    contentClass: item.adjudication?.content_class ?? item.content_class ?? 'unknown',
    biasReviewRequired:
      item.adjudication?.bias_review_required ??
      item.bias_review_required ??
      item.current_labels.bias_review_required ??
      false,
    labelOverrides:
      item.adjudication?.label_overrides ??
      Object.fromEntries(
        EDITABLE_LABEL_KEYS.map((labelKey) => [labelKey, Boolean(item.current_labels[labelKey])]),
      ),
    note: item.adjudication?.note ?? '',
  };
}

function CoveragePanel({
  title,
  values,
}: {
  title: string;
  values: Record<string, number>;
}) {
  const entries = Object.entries(values);
  return (
    <section className="coverage-panel">
      <div className="queue-header">
        <h2>{title}</h2>
        <span>{entries.length}</span>
      </div>
      <div className="coverage-list">
        {entries.length === 0 ? (
          <p className="queue-empty">No coverage summary available.</p>
        ) : (
          entries.map(([label, count]) => (
            <div key={label} className="coverage-row">
              <span>{label}</span>
              <strong>{count}</strong>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function QueueSection({
  title,
  queueName,
  items,
  drafts,
  onResolutionChange,
  onContentClassChange,
  onBiasReviewRequiredChange,
  onLabelOverrideChange,
  onNoteChange,
}: {
  title: string;
  queueName: AnnotationQueueName;
  items: QueueEntry[];
  drafts: Record<string, DecisionDraft>;
  onResolutionChange: (itemId: string, value: '' | AnnotationResolution) => void;
  onContentClassChange: (itemId: string, value: string) => void;
  onBiasReviewRequiredChange: (itemId: string, value: boolean) => void;
  onLabelOverrideChange: (itemId: string, labelKey: string, value: boolean) => void;
  onNoteChange: (itemId: string, value: string) => void;
}) {
  return (
    <section className="queue-panel">
      <div className="queue-header">
        <h2>{title}</h2>
        <span>{items.length}</span>
      </div>
      <div className="queue-list">
        {items.length === 0 ? (
          <p className="queue-empty">No items in this queue.</p>
        ) : (
          items.map((item) => {
            const draft = drafts[item.item_id] ?? buildDecisionDraft(item, queueName);
            return (
              <article key={item.item_id} className="queue-card">
                <div className="queue-card-meta">
                  <span>{item.item_id}</span>
                  {typeof item.weak_label_score === 'number' ? (
                    <strong>{item.weak_label_score.toFixed(2)}</strong>
                  ) : null}
                </div>
                <h3>{item.title}</h3>
                <div className="queue-stack">
                  {item.channel_name ? <p>Channel: {item.channel_name}</p> : null}
                  {item.content_class ? <p>Suggested class: {item.content_class}</p> : null}
                  {typeof item.content_class_confidence === 'number' ? (
                    <p>Class confidence: {item.content_class_confidence.toFixed(2)}</p>
                  ) : null}
                  {item.dominant_bias_risk ? <p>Dominant bias: {item.dominant_bias_risk}</p> : null}
                  {item.uncertainty_bucket ? <p>Bucket: {item.uncertainty_bucket}</p> : null}
                  {item.source_trust_flag ? <p>Trust flag: {item.source_trust_flag}</p> : null}
                  {item.template_cluster ? <p>Template: {item.template_cluster}</p> : null}
                  {typeof item.prior_flags === 'number' ? <p>Prior flags: {item.prior_flags}</p> : null}
                  {item.queue_reason ? <p>{item.queue_reason}</p> : null}
                  {item.annotator_notes.length > 0 ? (
                    <div className="note-list">
                      {item.annotator_notes.map((note) => (
                        <span key={note}>{note}</span>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className="decision-grid">
                  <label className="field-group">
                    <span>Resolution</span>
                    <select
                      value={draft.resolution}
                      onChange={(event) =>
                        onResolutionChange(item.item_id, event.target.value as '' | AnnotationResolution)
                      }
                    >
                      {RESOLUTION_OPTIONS.map((option) => (
                        <option key={option.label} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="field-group">
                    <span>Adjudicated class</span>
                    <select
                      value={draft.contentClass}
                      onChange={(event) => onContentClassChange(item.item_id, event.target.value)}
                    >
                      {CONTENT_CLASS_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="toggle-group">
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={draft.biasReviewRequired}
                      onChange={(event) =>
                        onBiasReviewRequiredChange(item.item_id, event.target.checked)
                      }
                    />
                    <span>Bias review required</span>
                  </label>
                  {EDITABLE_LABEL_KEYS.map((labelKey) => (
                    <label key={labelKey} className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.labelOverrides[labelKey])}
                        onChange={(event) =>
                          onLabelOverrideChange(item.item_id, labelKey, event.target.checked)
                        }
                      />
                      <span>{labelKey.replace(/_/g, ' ')}</span>
                    </label>
                  ))}
                </div>

                <label className="field-group">
                  <span>Reviewer note</span>
                  <textarea
                    value={draft.note}
                    onChange={(event) => onNoteChange(item.item_id, event.target.value)}
                    rows={3}
                    placeholder="Capture why this resolution is justified."
                  />
                </label>

                {item.adjudication ? (
                  <p className="saved-meta">
                    Saved: {item.adjudication.resolution} by {item.adjudication.reviewer ?? 'unknown reviewer'}
                  </p>
                ) : null}
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}

export function App() {
  const [batch, setBatch] = useState<AnnotationBatch | null>(null);
  const [drafts, setDrafts] = useState<Record<string, DecisionDraft>>({});
  const [reviewer, setReviewer] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadAnnotationBatch()
      .then((loadedBatch) => {
        setBatch(loadedBatch);
        setError(null);
        setDrafts(() => {
          const nextDrafts: Record<string, DecisionDraft> = {};
          for (const [queueName, items] of [
            ['review', loadedBatch.review_queue],
            ['hard-negative', loadedBatch.hard_negative_queue],
            ['disagreement', loadedBatch.disagreement_queue],
          ] as const) {
            for (const item of items) {
              nextDrafts[item.item_id] = buildDecisionDraft(item, queueName);
            }
          }
          return nextDrafts;
        });
      })
      .catch((loadError: Error) => {
        setError(loadError.message);
      });
  }, []);

  function updateDraft(itemId: string, updater: (draft: DecisionDraft) => DecisionDraft) {
    setDrafts((current) => {
      const existing = current[itemId];
      if (!existing) {
        return current;
      }
      return {
        ...current,
        [itemId]: updater(existing),
      };
    });
  }

  async function handleSave() {
    if (!batch) {
      return;
    }
    const decisions: AnnotationDecision[] = Object.values(drafts)
      .filter((draft) => draft.resolution !== '')
      .map((draft) => ({
        item_id: draft.itemId,
        queue_name: draft.queueName,
        resolution: draft.resolution as AnnotationResolution,
        content_class: draft.contentClass,
        label_overrides: draft.labelOverrides,
        bias_review_required: draft.biasReviewRequired,
        reviewer: reviewer.trim() || undefined,
        note: draft.note.trim() || undefined,
      }));
    if (decisions.length === 0) {
      setSaveMessage('Select at least one resolution before saving.');
      return;
    }
    setSaving(true);
    setSaveMessage(null);
    try {
      const response = await saveAnnotationAdjudications({
        run_id: batch.run_id,
        reviewer: reviewer.trim() || undefined,
        decisions,
      });
      const refreshedBatch = await loadAnnotationBatch();
      setBatch(refreshedBatch);
      setDrafts(() => {
        const nextDrafts: Record<string, DecisionDraft> = {};
        for (const [queueName, items] of [
          ['review', refreshedBatch.review_queue],
          ['hard-negative', refreshedBatch.hard_negative_queue],
          ['disagreement', refreshedBatch.disagreement_queue],
        ] as const) {
          for (const item of items) {
            nextDrafts[item.item_id] = buildDecisionDraft(item, queueName);
          }
        }
        return nextDrafts;
      });
      setSaveMessage(
        `Saved ${response.saved_count} adjudication(s) to ${response.adjudication_path}.`,
      );
      setError(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to save adjudications.');
    } finally {
      setSaving(false);
    }
  }

  if (error && !batch) {
    return <main className="app-shell error-shell">{error}</main>;
  }

  if (!batch) {
    return <main className="app-shell">Loading latest annotation batch…</main>;
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">TruthLens Labeling UI</p>
          <h1>Review queue for {batch.run_id}</h1>
          <p>
            Use this workspace to triage review items, inspect hard negatives, resolve disagreements,
            and persist adjudication decisions back into the dataset artifacts.
          </p>
          {batch.generated_at ? <p>Generated at: {batch.generated_at}</p> : null}
          {batch.source_batch_path ? <p>Batch source: {batch.source_batch_path}</p> : null}
          {batch.adjudication_path ? <p>Adjudication file: {batch.adjudication_path}</p> : null}
          {batch.gold_path ? <p>Gold labels: {batch.gold_path}</p> : null}
        </div>
        <div className="hero-stats">
          <div>
            <strong>{batch.review_queue.length}</strong>
            <span>Review</span>
          </div>
          <div>
            <strong>{batch.hard_negative_queue.length}</strong>
            <span>Hard negatives</span>
          </div>
          <div>
            <strong>{batch.disagreement_queue.length}</strong>
            <span>Disagreements</span>
          </div>
        </div>
      </header>

      <section className="notes-panel">
        <div className="queue-header">
          <h2>Adjudication</h2>
          <span>{batch.adjudication_summary?.confirmed_count ?? 0} saved</span>
        </div>
        <div className="review-toolbar">
          <label className="field-group toolbar-field">
            <span>Reviewer</span>
            <input
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              placeholder="Name or handle"
            />
          </label>
          <button type="button" className="primary-button" disabled={saving} onClick={handleSave}>
            {saving ? 'Saving…' : 'Save adjudications'}
          </button>
        </div>
        {saveMessage ? <p className="status-message success">{saveMessage}</p> : null}
        {error ? <p className="status-message error">{error}</p> : null}
        <div className="note-tags">
          {batch.annotator_notes_fields.map((field) => (
            <span key={field}>{field}</span>
          ))}
        </div>
        {batch.adjudication_summary ? (
          <div className="summary-grid">
            <div className="summary-card">
              <strong>{batch.adjudication_summary.confirmed_count}</strong>
              <span>Confirmed</span>
            </div>
            <div className="summary-card">
              <strong>{batch.adjudication_summary.escalation_count}</strong>
              <span>Escalations</span>
            </div>
            <div className="summary-card">
              <strong>{batch.adjudication_summary.unresolved_count}</strong>
              <span>Unresolved</span>
            </div>
          </div>
        ) : null}
      </section>

      <div className="coverage-grid">
        <CoveragePanel title="Content Class Coverage" values={batch.class_coverage} />
        <CoveragePanel title="Dominant Bias Coverage" values={batch.dominant_bias_coverage} />
      </div>

      <div className="queue-grid">
        <QueueSection
          title="Review Queue"
          queueName="review"
          items={batch.review_queue}
          drafts={drafts}
          onResolutionChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, resolution: value }))}
          onContentClassChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, contentClass: value }))}
          onBiasReviewRequiredChange={(itemId, value) =>
            updateDraft(itemId, (draft) => ({ ...draft, biasReviewRequired: value }))
          }
          onLabelOverrideChange={(itemId, labelKey, value) =>
            updateDraft(itemId, (draft) => ({
              ...draft,
              labelOverrides: { ...draft.labelOverrides, [labelKey]: value },
            }))
          }
          onNoteChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, note: value }))}
        />
        <QueueSection
          title="Hard Negative Queue"
          queueName="hard-negative"
          items={batch.hard_negative_queue}
          drafts={drafts}
          onResolutionChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, resolution: value }))}
          onContentClassChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, contentClass: value }))}
          onBiasReviewRequiredChange={(itemId, value) =>
            updateDraft(itemId, (draft) => ({ ...draft, biasReviewRequired: value }))
          }
          onLabelOverrideChange={(itemId, labelKey, value) =>
            updateDraft(itemId, (draft) => ({
              ...draft,
              labelOverrides: { ...draft.labelOverrides, [labelKey]: value },
            }))
          }
          onNoteChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, note: value }))}
        />
        <QueueSection
          title="Disagreement Queue"
          queueName="disagreement"
          items={batch.disagreement_queue}
          drafts={drafts}
          onResolutionChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, resolution: value }))}
          onContentClassChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, contentClass: value }))}
          onBiasReviewRequiredChange={(itemId, value) =>
            updateDraft(itemId, (draft) => ({ ...draft, biasReviewRequired: value }))
          }
          onLabelOverrideChange={(itemId, labelKey, value) =>
            updateDraft(itemId, (draft) => ({
              ...draft,
              labelOverrides: { ...draft.labelOverrides, [labelKey]: value },
            }))
          }
          onNoteChange={(itemId, value) => updateDraft(itemId, (draft) => ({ ...draft, note: value }))}
        />
      </div>
    </main>
  );
}
