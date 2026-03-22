import React from 'react';
import { createRoot } from 'react-dom/client';

function Popup() {
  return (
    <main style={{ fontFamily: 'Segoe UI, sans-serif', padding: 16, width: 280 }}>
      <h1>TruthLens</h1>
      <p>Bootstrap extension ready.</p>
      <p>Use the content script overlay on supported pages.</p>
    </main>
  );
}

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<Popup />);
}
