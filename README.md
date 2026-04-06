<p align="center">
  <img src="docs/logo/truthlens_logo.png" alt="TruthLens logo" width="220" />
</p>

# TruthLens

TruthLens is a multimodal browser-extension, API, trainer, and Android-share system for detecting, explaining, filtering, and supporting human review of misleading video packaging.

The repository already contains a hybrid scoring stack, optional learned paths, anomaly and history sidecars, BSEO policy/search code, trainer and simulation artifacts, explanation contracts, extension/mobile surfaces, and architecture tooling. This README is the GitHub-facing truth surface for what is actually committed now.

## Repo Status

Current committed root-repo truth:

- baseline runtime is separated into perception -> fusion/calibration -> selective verification -> policy -> explanation
- selective deep verification is explicit and fail-soft
- heavy LLM assistance remains downstream in review and report drafting, not in the baseline hot path
- BSEO exists in code and offline evaluation concepts, but the committed root runtime is still `threshold-default`
- no committed `configs/thresholds/bseo-policy.json` currently exists at repo root
- committed benchmark artifacts are tiny-sample and must not be read as production performance claims

## Architecture Summary

TruthLens runtime is organized as:

1. input and context
2. core multimodal perception
3. fusion and calibration
4. selective deep verification
5. policy and action selection
6. explanation and review provenance

BSEO is not the core classifier. It is placed as a bias-structured interpretation, policy, search, and artifact layer downstream of calibrated scoring.

Authoritative architecture references:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [Reference architecture](docs/architecture/REFERENCE_ARCHITECTURE.md)
- [Architecture diagnosis](docs/architecture/TRUTHLENS_ARCHITECTURE_REVISION_DIAGNOSIS.md)
- [Architecture visual notes](docs/architecture/README.md)

## Architecture Visual

![TruthLens architecture blueprint](docs/architecture/truthlens-architecture-blueprint.svg)

- [Mermaid source](docs/architecture/truthlens-architecture-blueprint.mmd)
- [SVG render](docs/architecture/truthlens-architecture-blueprint.svg)
- [PNG render](docs/architecture/truthlens-architecture-blueprint.png)

## Current Implemented Runtime

Committed baseline paths:

- text path
- vision path
- metadata path
- cross-signal mismatch logic

Committed optional sidecars and bounded learned paths:

- history path
- anomaly path
- sentence-transformer text path
- tiny-CNN and ViT thumbnail paths
- LSTM temporal history path

Committed downstream layers:

- fusion and calibration
- explicit selective deep verification triggers and provenance
- separate policy engine
- explanation engine with path, verification, and policy evidence
- human review and manual report flows

Not in the baseline hot path:

- Gemini report drafting assistance
- any always-on heavy LLM classifier
- unguarded BSEO-live takeover

## Policy Modes

Supported runtime modes in code:

- `threshold-default`
- `bseo-shadow`
- `bseo-live`

Compatibility aliases:

- `rl-shadow`
- `rl-live`

Committed root configuration today:

- `configs/thresholds/runtime-policy.json` is set to `threshold-default`
- root repo does not currently commit a `bseo-policy.json`
- README therefore does not present BSEO as the active committed runtime controller

## Benchmarking

Benchmark source of truth:

- [Benchmark README](docs/benchmarks/README.md)
- [Latest summary JSON](docs/benchmarks/latest/benchmark_summary.json)
- [Latest summary Markdown](docs/benchmarks/latest/benchmark_summary.md)

Current committed snapshot:

| Field | Value |
| --- | --- |
| `build_id` | `build-20260323000612` |
| `model_version` | `baseline-v1-build-20260323000612` |
| `trained_at` | `2026-03-23T00:06:12.500359+00:00` |
| `eval sample_count` | `4` |
| `configured runtime mode` | `threshold-default` |
| `resolved runtime mode` | `threshold-default` |

Current eval vs validation snapshot from committed artifacts:

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 1.000 | 0.000 |
| Recall | 1.000 | 0.000 |
| F1 | 1.000 | 0.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.000 | 0.000 |

## Metrics Caveats

These numbers are not production claims.

- committed eval sample count is only `4`
- validation performance is materially weaker than eval performance
- committed drift report compares against only `4` current rows
- committed simulation artifacts do not currently include populated BSEO lineage or mutation-atlas data
- README therefore surfaces benchmark truth as a tiny-sample artifact snapshot, not as a mature benchmark claim

## Evaluation And Visualization

### Overview

![Benchmark overview](docs/benchmarks/latest/assets/train_validation_eval_overview.svg)

### Per-Head Metrics

![Per-head metrics](docs/benchmarks/latest/assets/per_head_metrics.svg)

### Threshold Sweep

![Threshold sweep](docs/benchmarks/latest/assets/threshold_sweep.svg)

### Drift Summary

![Drift summary](docs/benchmarks/latest/assets/drift_summary.svg)

### Runtime Policy Truth

![Policy mode comparison](docs/benchmarks/latest/assets/policy_mode_comparison.svg)

Additional committed assets:

- [Overall metrics table](docs/benchmarks/latest/assets/overall_metrics_table.md)
- [Calibration error chart](docs/benchmarks/latest/assets/calibration_error.svg)
- [Confusion matrix](docs/benchmarks/latest/assets/confusion_matrix_eval.svg)
- [Benchmark provenance card](docs/benchmarks/latest/assets/benchmark_provenance.svg)
- [BSEO bias profile](docs/benchmarks/latest/assets/bseo_bias_profile.svg)
- [Mutation bias atlas](docs/benchmarks/latest/assets/mutation_bias_atlas.svg)
- [Lineage overview](docs/benchmarks/latest/assets/lineage_overview.svg)
- [Metrics dashboard](docs/benchmarks/latest/interactive/metrics_dashboard.html)
- [Threshold explorer](docs/benchmarks/latest/interactive/threshold_explorer.html)
- [BSEO policy dashboard](docs/benchmarks/latest/interactive/bseo_policy_dashboard.html)
- [Mutation atlas explorer](docs/benchmarks/latest/interactive/mutation_atlas.html)

## Artifact Provenance

Current benchmark inputs:

- `artifacts/trained_models/latest/model_info.json`
- `artifacts/eval_runs/build-20260323000612.json`
- `artifacts/eval_runs/build-20260323000612-simulation.json`
- `artifacts/drift_reports/build-20260323000612.json`
- `configs/thresholds/default.json`
- `configs/thresholds/runtime-policy.json`

Missing in the current committed root snapshot:

- `configs/thresholds/bseo-policy.json`
- committed BSEO report
- committed mutation-bias atlas
- committed lineage log

## Quick Start

### Python

```powershell
py -m uv sync --group dev
py -m uv run python scripts/run_api.py --reload
py -m uv run pytest -q
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
pnpm test:e2e
```

### Docs And Benchmark Assets

```powershell
pnpm docs:render-architecture
pnpm docs:render-benchmarks
```

### Training / Simulation Reproduction

```powershell
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.pipeline
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.train
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.simulate
```

## Repository Structure

- `apps/` runnable surfaces: API, extension, Android client, trainer, labeling UI
- `libs/` shared schemas, feature extraction, model serving, policy, explanation, evaluation, governance, data pipeline
- `configs/` thresholds and runtime/training configuration
- `artifacts/` trained models, eval runs, drift reports, exported runtime artifacts
- `docs/` architecture, benchmarks, and supporting documentation
- `tests/` unit, integration, and end-to-end verification

## V1 / V2 / V3 Alignment

`V1`

- explicit-feature bounded-path core
- text + vision + metadata + fusion + calibration
- extension + API + explanation baseline
- no mandatory deep verifier in hot path
- no runtime RL dependency

`V2`

- anomaly sidecar
- stronger history path
- transcript/title mismatch
- selective deep verification
- richer benchmark and visualization pipeline
- stronger human review flows

`V3`

- runtime-safe BSEO shadow/live policy
- mutation-bias atlas consumption when artifacts exist
- guarded policy optimization from evolution or bandit artifacts
- broader operator analytics

## Honest Limitations

- committed benchmarks are tiny-sample and unstable
- validation does not support any strong generalization claim yet
- root runtime config does not currently promote BSEO as the active committed policy artifact
- missing committed BSEO lineage and atlas artifacts means those visual panels are currently truthful stubs
- current repo truth is stronger on architecture separation than on benchmark maturity

## Next Stages

1. promote fresh committed BSEO artifacts only when lineage, atlas, and guardrails are actually present
2. grow the benchmark sample size and keep README aligned to the artifacts rather than to aspirational performance
3. continue hardening explanation provenance across extension, API, and Android review surfaces
