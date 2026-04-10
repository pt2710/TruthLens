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
const targetPngWidth = 3200;
const pngPadding = 48;

const diagramText = fs.readFileSync(inputPath, 'utf8');
const mermaidScript = fs.readFileSync(mermaidBundlePath, 'utf8');

const browser = await chromium.launch({
  executablePath: chromium.executablePath(),
  headless: true,
});

try {
  const page = await browser.newPage({
    viewport: { width: 3600, height: 4200 },
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
            padding: ${pngPadding}px;
            background: #ffffff;
          }
          svg {
            display: block;
            background: #ffffff;
            max-width: none !important;
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

  await page.evaluate(async ({ source, targetWidth }) => {
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

    const renderedSvg = app.querySelector('svg');
    if (!renderedSvg) {
      throw new Error('Architecture SVG was not rendered into the page.');
    }

    const viewBox = renderedSvg.getAttribute('viewBox');
    const [, , rawWidth, rawHeight] = (viewBox ?? '').split(/\s+/).map(Number);
    const aspectWidth = Number.isFinite(rawWidth) && rawWidth > 0 ? rawWidth : 1;
    const aspectHeight = Number.isFinite(rawHeight) && rawHeight > 0 ? rawHeight : 1;
    const targetHeight = Math.round((aspectHeight / aspectWidth) * targetWidth);

    renderedSvg.setAttribute('width', String(targetWidth));
    renderedSvg.setAttribute('height', String(targetHeight));
    renderedSvg.style.width = `${targetWidth}px`;
    renderedSvg.style.height = `${targetHeight}px`;
  }, { source: diagramText, targetWidth: targetPngWidth });

  const svg = await page.locator('#app svg').evaluate((node) => node.outerHTML);
  fs.writeFileSync(svgPath, svg, 'utf8');
  await page.locator('#app').screenshot({
    path: pngPath,
  });
} finally {
  await browser.close();
}
