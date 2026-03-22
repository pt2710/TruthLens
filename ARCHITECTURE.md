# TruthLens Architecture

## Mission

TruthLens is a multimodal system for detecting, explaining, filtering, and supporting semi-automated reporting of misleading video content through a browser extension and a model/policy backend.

## System Layers

1. Extension layer
2. Data discovery layer
3. Acquisition layer
4. Normalization layer
5. Dataset governance layer
6. Feature layer
7. Inference layer
8. Policy layer
9. Explanation layer
10. Feedback layer
11. Evaluation layer
12. Orchestration layer

## Repository Structure

The repository is organized as a monorepo with:

- `apps/` for runnable surfaces such as the API, extension, trainer, and labeling UI
- `libs/` for shared schemas, data pipeline code, governance, policy, explanation, model serving, and evaluation
- `infra/` for Docker, Compose, CI, DB, and migrations
- `configs/` for environment, threshold, model, labeling, and dataset configuration
- `datasets/` for tracked manifests/cards and untracked runtime data areas
- `artifacts/` for model and evaluation outputs
- `docs/` for architecture, API, workpacks, decisions, and subagent documentation
- `tests/` for unit, integration, e2e, and fixture coverage

## Core Contracts

- All scoring outputs must include `risk_score`, `confidence`, `uncertainty`, `recommended_action`, and `reasons`.
- Active recommendations require at least one explanation string.
- Auto-actions may not trigger from raw model score alone.
- Channel history is a supporting signal, not a sole verdict.
- Feedback events must be auditable and versioned.
- Model training is blocked until dataset governance artifacts are complete.

## V1 / V2 / V3 Boundaries

- V1: data pipelines, first dataset build, baseline models, calibration, FastAPI scoring, extension overlay, blur/hide, feedback capture, simple explanations
- V2: channel history, VAE anomaly signal, transcript-title mismatch, personalization, replay simulator
- V3: RL action policy, Bellman optimization, evolutionary search, cross-platform support, moderation-grade analytics

## Subagent-Friendly Boundaries

Safe parallelization targets:

- docs/bootstrap
- repo hygiene and CI
- data discovery / collection / normalization / auditing
- shared schemas
- extension scaffolding
- API scaffolding
- model research
- evaluation and simulation
