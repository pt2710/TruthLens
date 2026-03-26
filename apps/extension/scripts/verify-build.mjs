import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const extensionRoot = process.cwd();
const distDir = path.join(extensionRoot, 'dist');
const manifestPath = path.join(distDir, 'manifest.json');
const contentPath = path.join(distDir, 'content.js');

function fail(message) {
  console.error(message);
  process.exit(1);
}

if (!fs.existsSync(manifestPath)) {
  fail('Missing dist/manifest.json after extension build.');
}

if (!fs.existsSync(contentPath)) {
  fail('Missing dist/content.js after extension build.');
}

const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const contentScript = manifest.content_scripts?.find((entry) => Array.isArray(entry.js) && entry.js.includes('content.js'));
if (!contentScript) {
  fail('Manifest is missing content.js in content_scripts.');
}

if (!Array.isArray(contentScript.css) || !contentScript.css.includes('assets/content.css')) {
  fail('Manifest is missing assets/content.css for the content script.');
}

const contentCode = fs.readFileSync(contentPath, 'utf8').trimStart();
if (/^import(?:\s|\{|\*)/.test(contentCode)) {
  fail('dist/content.js still starts with an ESM import and will fail in Chrome content scripts.');
}

console.log('Extension build verified.');
