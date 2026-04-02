import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const rootDir = dirname(fileURLToPath(import.meta.url));
const browserDefines = {
  'process.env.NODE_ENV': JSON.stringify('production'),
};

export default defineConfig({
  plugins: [react()],
  define: browserDefines,
  resolve: {
    alias: {
      '@truthlens/shared-schemas': resolve(rootDir, '../../libs/shared-schemas/src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    lib: {
      entry: resolve(rootDir, 'src/content.tsx'),
      name: 'TruthLensContent',
      formats: ['iife'],
      fileName: () => 'content.js',
      cssFileName: 'content',
    },
    rollupOptions: {
      output: {
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
});
