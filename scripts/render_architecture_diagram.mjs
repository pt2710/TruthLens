import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
const inputPath = path.join(
  repoRoot,
  'docs',
  'architecture',
  'truthlens-architecture-blueprint.mmd',
);
const svgPath = path.join(
  repoRoot,
  'docs',
  'architecture',
  'truthlens-architecture-blueprint.svg',
);
const pngPath = path.join(
  repoRoot,
  'docs',
  'architecture',
  'truthlens-architecture-blueprint.png',
);
const mermaidBundlePath = require.resolve('mermaid/dist/mermaid.min.js');

const diagramText = fs.readFileSync(inputPath, 'utf8');
const mermaidScript = fs.readFileSync(mermaidBundlePath, 'utf8');

const browser = await chromium.launch({
  executablePath: chromium.executablePath(),
  headless: true,
});

try {
  const page = await browser.newPage({
    viewport: { width: 2600, height: 3600 },
    deviceScaleFactor: 2,
  });

  await page.setContent(
    `<!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body {
            margin: 0;
            background: #ffffff;
            font-family: Arial, Helvetica, sans-serif;
          }
          #app {
            width: max-content;
            padding: 24px;
            background: #ffffff;
          }
          svg {
            display: block;
            background: #ffffff;
          }
        </style>
      </head>
      <body>
        <div id="app"></div>
        <script>${mermaidScript}</script>
      </body>
    </html>`,
    { waitUntil: 'load' },
  );

  await page.evaluate(async (source) => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'loose',
      theme: 'base',
      flowchart: {
        curve: 'linear',
        htmlLabels: true,
      },
    });

    const { svg } = await mermaid.render('truthlensArchitecture', source);
    const app = document.getElementById('app');
    if (!app) {
      throw new Error('Architecture render root was not found.');
    }
    app.innerHTML = svg;
  }, diagramText);

  const svg = await page.locator('#app svg').evaluate((node) => node.outerHTML);
  fs.writeFileSync(svgPath, svg, 'utf8');

  const box = await page.locator('#app svg').boundingBox();
  if (!box) {
    throw new Error(
      'Rendered architecture diagram did not produce a visible SVG.',
    );
  }

  const padding = 16;
  await page.screenshot({
    path: pngPath,
    clip: {
      x: Math.max(box.x - padding, 0),
      y: Math.max(box.y - padding, 0),
      width: box.width + padding * 2,
      height: box.height + padding * 2,
    },
  });
} finally {
  await browser.close();
}
