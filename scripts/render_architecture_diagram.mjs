import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
const mermaidBundlePath = require.resolve('mermaid/dist/mermaid.min.js');
const mermaidScript = fs.readFileSync(mermaidBundlePath, 'utf8');

const diagrams = [
  {
    name: 'truthlensArchitectureOverview',
    inputPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-architecture-blueprint.mmd'),
    svgPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-architecture-blueprint.svg'),
    pngPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-architecture-blueprint.png'),
    targetWidth: 2400,
    viewport: { width: 2800, height: 2200 },
    padding: 44,
  },
  {
    name: 'truthlensRuntimeDecisionFlow',
    inputPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-runtime-decision-flow.mmd'),
    svgPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-runtime-decision-flow.svg'),
    pngPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-runtime-decision-flow.png'),
    targetWidth: 2400,
    viewport: { width: 2800, height: 1800 },
    padding: 44,
  },
  {
    name: 'truthlensGovernanceFeedbackLoop',
    inputPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-governance-feedback-loop.mmd'),
    svgPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-governance-feedback-loop.svg'),
    pngPath: path.join(repoRoot, 'docs', 'architecture', 'truthlens-governance-feedback-loop.png'),
    targetWidth: 2400,
    viewport: { width: 2800, height: 2000 },
    padding: 44,
  },
];

const browser = await chromium.launch({
  executablePath: chromium.executablePath(),
  headless: true,
});

async function renderDiagram(diagram) {
  const page = await browser.newPage({
    viewport: diagram.viewport,
    deviceScaleFactor: 2,
  });

  try {
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
              padding: ${diagram.padding}px;
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

    const source = fs.readFileSync(diagram.inputPath, 'utf8');
    await page.evaluate(async ({ id, sourceText, targetWidth }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'loose',
        theme: 'base',
        flowchart: {
          curve: 'basis',
          htmlLabels: true,
        },
      });

      const { svg } = await mermaid.render(id, sourceText);
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
      renderedSvg.style.maxWidth = 'none';
    }, { id: diagram.name, sourceText: source, targetWidth: diagram.targetWidth });

    const svg = await page.locator('#app svg').evaluate((node) => node.outerHTML);
    fs.writeFileSync(diagram.svgPath, svg, 'utf8');
    await page.locator('#app').screenshot({
      path: diagram.pngPath,
    });
  } finally {
    await page.close();
  }
}

try {
  for (const diagram of diagrams) {
    await renderDiagram(diagram);
  }
} finally {
  await browser.close();
}
