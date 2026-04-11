# Extension Beta Install

TruthLens' first external beta is extension-only and expects a hosted API.
The supported install path is a hosted API plus unpacked Chromium extension.
There is no committed live default hostname in the public repo. External beta bundles must be pointed at the real hosted origin explicitly.

## What this beta includes

- feed and watch-page scoring on YouTube
- visible warning-state actions and explanations
- manual report drafting and optimization
- browser observation and feedback intake

## What this beta does not include

- browser-store distribution
- Android as a public beta surface
- direct YouTube OAuth/report-submit as a supported hosted-beta contract

## Install the extension

1. Set the live hosted beta origin for the build:

   ```powershell
   $env:VITE_TRUTHLENS_API_BASE="https://<your-live-hosted-beta-origin>"
   ```

2. Build the extension bundle:

   ```powershell
   pnpm install
   pnpm --filter @truthlens/extension build
   ```

3. Open `chrome://extensions`
4. Turn on `Developer mode`
5. Choose `Load unpacked`
6. Select `apps/extension/dist`

## Expected beta boundaries

- if Gemini is not configured server-side, TruthLens falls back to heuristic draft suggestions
- if direct YouTube API reporting is unavailable or disabled, TruthLens falls back to manual/page-level review flows
- if no live hosted beta origin is configured at build time, the extension cannot be treated as a real external beta build
- benchmark visuals in the repo are engineering truth surfaces, not mass-market claims

## If you are running locally instead

Local development still uses the API on `http://127.0.0.1:8000` by default for Vite dev builds:

```powershell
py -m uv sync --group dev
py -m uv run python scripts/run_api.py --reload
pnpm install
pnpm --filter @truthlens/extension build
```
