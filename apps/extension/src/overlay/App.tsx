import { useOverlayStore } from './store';

export function App() {
  const { flaggedCount, itemCount, lastScore } = useOverlayStore();

  return (
    <aside className="truthlens-panel">
      <h1>TruthLens</h1>
      <p>Scanned items: {itemCount}</p>
      <p>Flagged items: {flaggedCount}</p>
      {lastScore ? (
        <>
          <p>Latest risk: {lastScore.risk_score}</p>
          <p>Action: {lastScore.recommended_action}</p>
          {lastScore.explanation_summary ? <p>Why: {lastScore.explanation_summary}</p> : null}
        </>
      ) : (
        <p>No items scored yet.</p>
      )}
    </aside>
  );
}
