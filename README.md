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
- a compatible `configs/thresholds/bseo-policy.json` is now committed and the root runtime is promoted to `bseo-shadow`
- `bseo-live` is still intentionally blocked by governance because committed shadow-observation history is still far below the live threshold
- committed benchmarks are larger than the earlier tiny-sample snapshot, but they are still repository artifacts rather than production performance claims

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
- browser observation records with shared provenance and distilled DOM features
- feedback-linked supplemental label candidates and split-safe adjudication intake
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

- `configs/thresholds/runtime-policy.json` is set to `bseo-shadow`
- `configs/thresholds/bseo-policy.json` is committed and contract-compatible with the current runtime
- `bseo-live` is not promoted yet because runtime governance still blocks live rollout on shadow-observation soak

## Observation And Feedback Intake

TruthLens now treats browser observation and feedback-to-dataset as one shared intake path rather than two disconnected side systems.

- the extension can persist DOM-based browser observation records without any DevTools dependency
- observation records, feedback events, and supplemental label candidates share provenance-aware contracts
- linked feedback and manual reports can create supplemental adjudication candidates in the labeling UI
- those supplemental candidates are explicitly split-blocked and do not append directly to `train`, `validation`, or `test`
- adjudicated supplemental rows land in separate intake artifacts and require future deterministic ingestion before any training use

## Benchmarking

Benchmark source of truth:

- [Benchmark README](docs/benchmarks/README.md)
- [Latest summary JSON](docs/benchmarks/latest/benchmark_summary.json)
- [Latest summary Markdown](docs/benchmarks/latest/benchmark_summary.md)
- [Latest verify JSON](docs/benchmarks/latest/verify_summary.json)
- [Latest verify Markdown](docs/benchmarks/latest/verify_summary.md)

Current committed snapshot:

| Field | Value |
| --- | --- |
| `build_id` | `build-20260406042818` |
| `model_version` | `baseline-v1-build-20260406042818` |
| `trained_at` | `2026-04-06T04:28:18.606357+00:00` |
| `eval sample_count` | `44` |
| `configured runtime mode` | `bseo-shadow` |
| `resolved runtime mode` | `bseo-shadow` |
| `governance recommended mode` | `bseo-shadow` |
| `max promotable mode` | `bseo-shadow` |

Current eval vs validation snapshot from committed artifacts:

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 1.000 | 1.000 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 1.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.220 | 0.220 |

## Metrics Caveats

These numbers are not production claims.

- committed eval sample count is now `44`, which is materially better than the earlier tiny-sample snapshot but still modest
- eval and validation are both very strong on this committed split; that symmetry should be read as a clean repository benchmark, not as broad real-world proof
- overall calibration error remains `0.220`, so ranking confidence is still less mature than the binary F1 snapshot suggests
- per-head metrics are uneven: text/fusion are strong, while history and anomaly remain much weaker sidecars
- `bseo-live` is still blocked because committed shadow-observation history is still far below the live threshold of `200`

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

### Runtime Governance

![Runtime governance summary](docs/benchmarks/latest/assets/runtime_governance.svg)

### Observation And Feedback Intake

![Observation and feedback intake](docs/benchmarks/latest/assets/observation_feedback_intake.svg)

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
- [Runtime governance dashboard](docs/benchmarks/latest/interactive/runtime_governance_dashboard.html)
- [Observation and feedback intake summary](docs/benchmarks/latest/assets/observation_feedback_intake.svg)

## Artifact Provenance

Current benchmark inputs:

- `artifacts/trained_models/latest/model_info.json`
- `artifacts/eval_runs/build-20260406042818.json`
- `artifacts/eval_runs/build-20260406042818-simulation.json`
- `artifacts/eval_runs/build-20260406042818-bseo-report.json`
- `artifacts/eval_runs/build-20260406042818-bseo-lineage.json`
- `artifacts/eval_runs/build-20260406042818-mutation-bias-atlas.json`
- `artifacts/drift_reports/build-20260406042818.json`
- `configs/thresholds/default.json`
- `configs/thresholds/bseo-policy.json`
- `configs/thresholds/runtime-policy.json`
- `artifacts/reports/runtime-governance-latest.json`
- `artifacts/reports/browser_observations.jsonl` when browser observation intake has been exercised
- `datasets/labels/supplemental_candidates/latest.json` when supplemental candidates have been derived
- `datasets/labels/supplemental_adjudication/*.json` and `datasets/labels/supplemental_gold/*.jsonl` for split-blocked supplemental adjudication

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
pnpm runtime:promote-auto
pnpm docs:render-architecture
pnpm docs:render-benchmarks
pnpm docs:render-verify
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

- committed benchmarks are stronger than before but still small enough that README should not read like a product benchmark sheet
- calibration and per-head stability still lag behind the clean fused F1 snapshot
- history and anomaly paths remain useful sidecars, not equally mature peers to text and fusion
- `bseo-shadow` is promoted, but `bseo-live` still lacks the shadow-soak evidence required for a truthful rollout
- observation and supplemental intake artifacts depend on actual runtime use, so a clean repo snapshot may legitimately show zero supplemental volume
- current repo truth is stronger on architecture separation and governance discipline than on large-sample benchmark maturity

## Next Stages

1. accumulate real shadow-observation history and only then reconsider `bseo-live`
2. grow benchmark coverage beyond the current `44` eval rows so README metrics become less brittle
3. keep turning benchmark and provenance artifacts into richer operator dashboards and runtime governance views
