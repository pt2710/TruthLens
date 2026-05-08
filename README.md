<p align="center">
  <img src="docs/logo/truthlens_logo.png" alt="TruthLens logo" width="560" />
</p>

# TruthLens

TruthLens is a multimodal browser-extension, API, trainer, and Android-share repository for detecting misleading video packaging, supporting human review, and applying a local user-side reranking layer on top of platform feeds.

The primary public-facing presentation surface now lives in [docs/index.html](docs/index.html). This README is the repo-facing truth surface: identity, onboarding, supported surfaces, and links into the committed docs and benchmark artifacts.

## First 60 Seconds

- TruthLens is currently a hosted/open beta codebase, not production-grade software or a broad public launch.
- Feed scoring and reranking happen locally in the extension on top of what YouTube already showed the current user.
- TruthLens truth score is user-facing: `10.0` is best, `0.0` is worst.
- Report and verify sheets open only on explicit user action.
- TruthLens-assisted reporting is currently human-assisted manual submission, not autonomous reporting.
- Metrics are artifact-backed benchmark truth, not generalized production claims.
- Committed benchmark truth lives under `docs/benchmarks/latest/` and is guarded by `python scripts/benchmark_freshness_gate.py`.

## Public Surfaces

- Landing page: [docs/index.html](docs/index.html)
- GitHub Pages deployment: succeeds once repository Pages is enabled in Settings, or when `PAGES_ADMIN_TOKEN` is provided for first-time enablement from Actions
- Extension beta install: [docs/beta-install.md](docs/beta-install.md)
- Hosted beta contract: [docs/deployment/render-beta.md](docs/deployment/render-beta.md)
- Hosted beta verification: [docs/deployment/hosted-beta-verification.md](docs/deployment/hosted-beta-verification.md)
- Privacy and dataflow note: [docs/privacy-dataflow.md](docs/privacy-dataflow.md)
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

## Quick Start: Hosted Beta Extension Test

This path is for external beta testers who want to load the Chromium extension against the hosted beta API.

```powershell
git clone https://github.com/pt2710/TruthLens.git
cd TruthLens
pnpm install
pnpm --filter @truthlens/extension build
```

Then open Chromium or Chrome:

```text
chrome://extensions
Developer mode: ON
Load unpacked
Select: apps/extension/dist
```

Beta testers do not need local Gemini, YouTube, Render, Postgres, or API secrets for this hosted beta extension path. The production extension build uses the committed hosted beta API default unless an operator explicitly overrides `VITE_TRUTHLENS_API_BASE`.

This remains a hosted/open beta, not a production release. Local backend setup is only needed for contributors working on API, scoring, governance, or deployment code.

## Developer Setup

TruthLens uses `pnpm` for Node workspaces and `uv` for Python tooling.

```powershell
pnpm install
py -m uv sync
```

Common verification commands:

```powershell
py -m uv run pytest tests
py -m uv run ruff check .
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Python dependencies are governed by `pyproject.toml` and `uv.lock`. There is no canonical `requirements.txt`; one is not needed for hosted beta extension testing. If a compatibility export is added later, `pyproject.toml` and `uv.lock` should remain the source of truth.

Node dependencies are governed by `package.json`, package workspace manifests, and `pnpm-lock.yaml`. The extension build output is `apps/extension/dist`.

## Architecture Overview

The current architecture diagrams are source-generated from Mermaid files under `docs/architecture/` and rendered as committed SVG/PNG assets.

![TruthLens architecture overview](docs/architecture/truthlens-architecture-blueprint.png)

![TruthLens runtime decision flow](docs/architecture/truthlens-runtime-decision-flow.png)

![TruthLens governance feedback loop](docs/architecture/truthlens-governance-feedback-loop.png)

These diagrams show the hosted Render API, Chromium extension beta, ad/non-video filtering, local user-side reranking, Adaptive Semantic Evidence Routing, BSEO as downstream policy, human-assisted reporting, event capture, and governed benchmark truth surfaces.

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
- Semantic routing dashboard: [docs/benchmarks/latest/interactive/semantic_routing_dashboard.html](docs/benchmarks/latest/interactive/semantic_routing_dashboard.html)
- Runtime governance artifact: [artifacts/reports/runtime-governance-latest.json](artifacts/reports/runtime-governance-latest.json)
- Freshness gate: `python scripts/benchmark_freshness_gate.py`

## Docs

- Architecture docs: [docs/architecture/README.md](docs/architecture/README.md)
- Benchmarks docs: [docs/benchmarks/README.md](docs/benchmarks/README.md)
- Deployment docs: [docs/deployment/](docs/deployment)
- Decision records: [docs/decision-records/](docs/decision-records)

## Developer Checks

```powershell
py -m uv run python scripts/release_hygiene_audit.py
py -m uv run pytest tests
py -m uv run ruff check .
pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
py -m uv run python scripts/benchmark_freshness_gate.py
```

## Repo Truth Notes

- Direct YouTube API reporting remains deployment- and account-dependent.
- TruthLens can fall back to YouTube’s in-page report flow when direct API reporting is unavailable.
- Creator/operator benchmark truth is kept separate from ordinary local-user optimization feedback.
- Ordinary public/test-user local feedback is supplemental runtime evidence unless a controlled adjudication path promotes it.
- README should stay repo-like; public rationale and project presentation belong on the landing page and linked docs.
