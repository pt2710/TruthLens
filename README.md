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
```

### TypeScript

```powershell
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## Core Documents

- `AGENTS.md`
- `CODEX_WORKFLOW.md`
- `ARCHITECTURE.md`
- `CONTRIBUTING.md`
