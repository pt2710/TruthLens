# TruthLens

TruthLens is a multimodal browser-plugin and backend system for detection, filtering, explanation, and semi-automated reporting support for misleading video content.

## Repository Goals

- Bootstrap a Codex-ready monorepo under `TruthLens/`
- Provide a FastAPI scoring backend with explicit score and feedback contracts
- Provide a browser extension shell with DOM observation, overlays, blur/hide flows, and feedback capture
- Establish data discovery, acquisition, normalization, governance, and audit scaffolding before model training

## Quick Start

### Python

```powershell
py -m uv sync --group dev
py -m uv run pytest
py -m uv run ruff check .
py -m uv run mypy .
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.pipeline
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.train
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.simulate
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.smoke
```

### TypeScript

```powershell
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
pnpm build
```

## Core Documents

- `AGENTS.md`
- `CODEX_WORKFLOW.md`
- `ARCHITECTURE.md`
- `CONTRIBUTING.md`

## Current End-to-End Bootstrap Flow

1. `truthlens_trainer.pipeline` builds discovery, acquisition, normalization, label prep, deduplication, split manifests, dataset card, and audit outputs.
2. `truthlens_trainer.train` trains bootstrap text, vision, metadata, fusion, and calibration heads and exports model artifacts.
3. `truthlens_trainer.simulate` runs threshold sweep, Q-table policy bootstrap, threshold search, and drift reporting.
4. `truthlens_api.main` serves scoring, batch scoring, feedback, health, model info, and policy info.
5. The extension content script scores feed cards through the API with local fallback and captures user feedback events.

## Smoke Validation

Run the full local smoke chain in one command:

```powershell
make smoke
```

This runs dataset build, model training, simulation, and API endpoint validation in an isolated smoke root and writes a report to `artifacts/reports/smoke-summary.json` inside that isolated run.
