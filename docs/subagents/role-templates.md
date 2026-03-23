# TruthLens Subagent Role Templates

These templates operationalize Workpack 20 and are aligned with `AGENTS.md` and `CODEX_WORKFLOW.md`.

## Docs Bootstrap

- Scope: `AGENTS.md`, `CODEX_WORKFLOW.md`, `ARCHITECTURE.md`, repo governance docs.
- Writable paths: `docs/`, top-level docs, `.codex/agents/`.
- Deliverable: concise summary of contracts added or updated.

## Repo Hygiene

- Scope: formatter, lint, CI, hooks, lockfiles, reproducibility issues.
- Writable paths: root config, `infra/ci/`, `.github/workflows/`.
- Deliverable: concrete check matrix and failure notes.

## Data Scout

- Scope: source manifests, discovery coverage, refresh candidates.
- Writable paths: `libs/data-pipeline/`, `configs/datasets/`, `datasets/raw/source_manifests/`.
- Deliverable: source manifest delta, risks, expected fields.

## Data Collector

- Scope: raw acquisition, retries, collection manifests, quarantine rules.
- Writable paths: `libs/data-pipeline/`, `datasets/raw/`, `artifacts/data_reports/`.
- Deliverable: success/failure counts and raw artifact paths.

## Data Normalizer

- Scope: schema harmonization, fingerprints, missing field markers, interim records.
- Writable paths: `libs/data-pipeline/`, `datasets/interim/`, `datasets/manifests/transforms/`.
- Deliverable: transform manifest and schema notes.

## Data Auditor

- Scope: deduplication, leakage checks, split integrity, audit reports.
- Writable paths: `libs/dataset-governance/`, `datasets/manifests/audits/`, `artifacts/data_quality/`.
- Deliverable: duplicate rate, leakage status, remaining risks.

## Label Prep

- Scope: annotation batches, disagreement queues, hard negatives, provenance.
- Writable paths: `libs/data-pipeline/`, `datasets/labels/`, `configs/labeling/`.
- Deliverable: batch counts and review-load summary.

## Dataset Builder

- Scope: processed splits, build manifests, dataset cards, train gates.
- Writable paths: `libs/dataset-governance/`, `datasets/processed/`, `datasets/dataset_cards/`.
- Deliverable: build ID, split counts, gate status.

## Extension

- Scope: DOM observer, selectors, overlay UI, API adapter, local cache.
- Writable paths: `apps/extension/`, `tests/e2e/`, `tests/fixtures/`.
- Deliverable: user-visible behavior, failure fallback, test status.

## API

- Scope: FastAPI contracts, model serving, feedback persistence, health/info endpoints.
- Writable paths: `apps/api/`, `libs/model-serving/`, `libs/policy-engine/`, `libs/explanation-engine/`.
- Deliverable: endpoint delta and contract impact.

## Model Research

- Scope: baseline text, vision, metadata, fusion, calibration artifacts.
- Writable paths: `apps/trainer/`, `libs/model-serving/`, `artifacts/trained_models/`, `artifacts/eval_runs/`.
- Deliverable: metrics snapshot and artifact locations.

## Eval / Simulation

- Scope: replay, threshold sweeps, RL prototype, evolutionary search, drift reports.
- Writable paths: `libs/evaluation/`, `artifacts/eval_runs/`, `artifacts/drift_reports/`.
- Deliverable: recommended thresholds, cost tradeoffs, drift summary.
