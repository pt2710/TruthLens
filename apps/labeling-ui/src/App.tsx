import { useEffect, useState } from 'react';

import { type AnnotationBatch, type QueueEntry, loadAnnotationBatch } from './lib/annotationBatch';
import './styles.css';

function QueueSection({ title, items }: { title: string; items: QueueEntry[] }) {
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
          items.map((item) => (
            <article key={item.item_id} className="queue-card">
              <div className="queue-card-meta">
                <span>{item.item_id}</span>
                {typeof item.weak_label_score === 'number' ? (
                  <strong>{item.weak_label_score.toFixed(2)}</strong>
                ) : null}
              </div>
              <h3>{item.title}</h3>
              {item.channel_name ? <p>Channel: {item.channel_name}</p> : null}
              {item.uncertainty_bucket ? <p>Bucket: {item.uncertainty_bucket}</p> : null}
              {item.source_trust_flag ? <p>Trust flag: {item.source_trust_flag}</p> : null}
              {item.template_cluster ? <p>Template: {item.template_cluster}</p> : null}
              {typeof item.prior_flags === 'number' ? <p>Prior flags: {item.prior_flags}</p> : null}
              {item.queue_reason ? <p>{item.queue_reason}</p> : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}

export function App() {
  const [batch, setBatch] = useState<AnnotationBatch | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAnnotationBatch()
      .then(setBatch)
      .catch((loadError: Error) => {
        setError(loadError.message);
      });
  }, []);

  if (error) {
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
            Use this workspace to triage review items, inspect hard negatives, and track disagreement
            lanes before adjudication.
          </p>
          {batch.generated_at ? <p>Generated at: {batch.generated_at}</p> : null}
          {batch.source_batch_path ? <p>Batch source: {batch.source_batch_path}</p> : null}
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
        <h2>Annotator note fields</h2>
        <div className="note-tags">
          {batch.annotator_notes_fields.map((field) => (
            <span key={field}>{field}</span>
          ))}
        </div>
      </section>
      <div className="queue-grid">
        <QueueSection title="Review Queue" items={batch.review_queue} />
        <QueueSection title="Hard Negative Queue" items={batch.hard_negative_queue} />
        <QueueSection title="Disagreement Queue" items={batch.disagreement_queue} />
      </div>
    </main>
  );
}
