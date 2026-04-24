<p align="center">
  <img src="docs/logo/truthlens_logo.png" alt="TruthLens logo" width="220" />
</p>

# TruthLens

TruthLens is a multimodal browser-extension, API, trainer, and Android-share repository for detecting misleading video packaging, supporting human review, and applying a local user-side reranking layer on top of platform feeds.

The primary public-facing presentation surface now lives in [docs/index.html](docs/index.html). This README is the repo-facing truth surface: identity, onboarding, supported surfaces, and links into the committed docs and benchmark artifacts.

## First 60 Seconds

- TruthLens is currently a controlled extension-first hosted beta, not a broad public launch.
- Feed scoring and reranking happen locally in the extension on top of what YouTube already showed the current user.
- TruthLens truth score is user-facing: `10.0` is best, `0.0` is worst.
- Report and verify sheets open only on explicit user action.
- TruthLens-assisted reporting is currently human-assisted manual submission, not autonomous reporting.
- Committed benchmark truth lives under `docs/benchmarks/latest/` and is guarded by `python scripts/benchmark_freshness_gate.py`.

## Public Surfaces

- Landing page: [docs/index.html](docs/index.html)
- GitHub Pages deployment: succeeds once repository Pages is enabled in Settings, or when `PAGES_ADMIN_TOKEN` is provided for first-time enablement from Actions
- Extension beta install: [docs/beta-install.md](docs/beta-install.md)
- Hosted beta contract: [docs/deployment/render-beta.md](docs/deployment/render-beta.md)
- Hosted beta verification: [docs/deployment/hosted-beta-verification.md](docs/deployment/hosted-beta-verification.md)
- Public hardening audit: [docs/decision-records/wave1-public-hardening-audit.md](docs/decision-records/wave1-public-hardening-audit.md)

## Repo Layout

- `apps/`: runnable surfaces such as API, extension, trainer, Android client, and labeling UI
- `libs/`: shared schemas, feature extraction, policy, evaluation, governance, and model-serving code
- `configs/`: runtime and training thresholds and policies
- `artifacts/`: trained models, eval outputs, drift reports, and runtime promotion artifacts
- `datasets/`: committed manifests and curated governance truth, not raw unaudited datasets
- `docs/`: public landing page, architecture docs, benchmarks, deployment docs, and decision records
- `tests/`: unit and end-to-end verification

## Supported Surfaces

| Surface | Status |
| --- | --- |
| Chromium desktop extension on YouTube | first supported external beta surface |
| Hosted API | required for beta |
| Android share client | internal / experimental |
| Firefox | not committed as supported |
| iOS | not committed as supported |

## Extension Beta Quick Start

1. Read the hosted deployment contract: [docs/deployment/render-beta.md](docs/deployment/render-beta.md)
2. Read the tester install path: [docs/beta-install.md](docs/beta-install.md)
3. Install dependencies: `pnpm install` and `python -m uv sync --group dev`
4. Build the extension: `pnpm --filter @truthlens/extension build`
5. Load the unpacked extension in Chromium and point it at the configured TruthLens API origin

## Runtime And UI Truth

- The chip on each feed card shows the user-facing TruthLens truth score.
- Badge colors follow the product contract:
  - `0.0-3.3` red
  - `3.4-4.9` orange
  - `5.0-6.6` yellow
  - `6.7-10.0` green
- Local reranking is a browser-side ordering layer only. It does not alter YouTube’s backend recommender.
- `recommended_action = blur` remains an internal policy label, but the extension keeps thumbnails visible and presents that state as a warning.
- Manual review can be opened from:
  - the `Review report` / `Verify transparent` badge
  - the TruthLens right-click entry on a specific thumbnail

## Benchmark Truth

- Latest committed benchmark summary: [docs/benchmarks/latest/benchmark_summary.json](docs/benchmarks/latest/benchmark_summary.json)
- Latest committed verify summary: [docs/benchmarks/latest/verify_summary.json](docs/benchmarks/latest/verify_summary.json)
- Benchmark visuals: [docs/benchmarks/latest/assets/](docs/benchmarks/latest/assets)
- Runtime governance artifact: [artifacts/reports/runtime-governance-latest.json](artifacts/reports/runtime-governance-latest.json)
- Freshness gate: `python scripts/benchmark_freshness_gate.py`

## Docs

- Architecture docs: [docs/architecture/README.md](docs/architecture/README.md)
- Benchmarks docs: [docs/benchmarks/README.md](docs/benchmarks/README.md)
- Deployment docs: [docs/deployment/](docs/deployment)
- Decision records: [docs/decision-records/](docs/decision-records)

## Developer Checks

```powershell
python scripts/release_hygiene_audit.py
python -m uv run pytest
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
python scripts/benchmark_freshness_gate.py
```

## Repo Truth Notes

- Direct YouTube API reporting remains deployment- and account-dependent.
- TruthLens can fall back to YouTube’s in-page report flow when direct API reporting is unavailable.
- Creator/operator benchmark truth is kept separate from ordinary local-user optimization feedback.
- README should stay repo-like; public rationale and project presentation belong on the landing page and linked docs.
