import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

const rootDir = dirname(fileURLToPath(import.meta.url));
const annotationAssetName = 'annotation-batch.data.json';
const datasetAnnotationPath = resolve(
  rootDir,
  '..',
  '..',
  'datasets',
  'labels',
  'annotation_batches',
  'latest.json',
);
const fallbackAnnotationPath = resolve(rootDir, 'public', 'annotation-batch.json');

async function loadAnnotationBatchSource(): Promise<string> {
  const sourcePath = existsSync(datasetAnnotationPath) ? datasetAnnotationPath : fallbackAnnotationPath;
  return readFile(sourcePath, 'utf-8');
}

function annotationBatchPlugin(): Plugin {
  return {
    name: 'truthlens-annotation-batch',
    configureServer(server) {
      server.middlewares.use(`/${annotationAssetName}`, async (_req, res) => {
        const source = await loadAnnotationBatchSource();
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
        res.end(source);
      });
    },
    async generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: annotationAssetName,
        source: await loadAnnotationBatchSource(),
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), annotationBatchPlugin()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': resolve(rootDir, 'src'),
    },
  },
});
