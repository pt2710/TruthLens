# Extension Beta Install

TruthLens' first external beta is extension-only and uses the hosted beta API by default for production extension builds.
The supported install path is the hosted API plus an unpacked Chromium extension.
The committed hosted beta origin is `https://truthlens-beta-api.onrender.com`; operators can override it with `VITE_TRUTHLENS_API_BASE` when building a private or staging bundle.

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

1. Install Node dependencies and build the extension bundle:

   ```powershell
   git clone https://github.com/pt2710/TruthLens.git
   cd TruthLens
   pnpm install
   pnpm --filter @truthlens/extension build
   ```

2. Open `chrome://extensions`
3. Turn on `Developer mode`
4. Choose `Load unpacked`
5. Select `apps/extension/dist`

## Expected beta boundaries

- if Gemini is not configured server-side, TruthLens falls back to heuristic draft suggestions
- if direct YouTube API reporting is unavailable or disabled, TruthLens falls back to manual/page-level review flows
- beta testers do not need local Gemini, YouTube, Render, Postgres, or API secrets for the hosted extension path
- local backend setup is only needed for contributors or operators testing API/deployment changes
- benchmark visuals in the repo are engineering truth surfaces, not mass-market claims

## If you are running locally instead

Local development still uses the API on `http://127.0.0.1:8000` by default for Vite dev builds:

```powershell
py -m uv sync --group dev
py -m uv run python scripts/run_api.py --reload
pnpm install
pnpm --filter @truthlens/extension build
```
