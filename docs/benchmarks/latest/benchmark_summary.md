# Benchmark Summary

- Generated at: `2026-04-06T04:49:36.017741+00:00`
- Build ID: `build-20260406042818`
- Model version: `baseline-v1-build-20260406042818`
- Eval sample count: `44`
- Configured runtime policy mode: `bseo-shadow`
- Resolved runtime policy mode: `bseo-shadow`
- Governance recommended mode: `bseo-shadow`
- Max promotable mode: `bseo-shadow`

## Metrics

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 1.000 | 1.000 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 1.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.220 | 0.220 |

## Runtime Governance

- Shadow eligible: `True`
- Live eligible: `False`
- Live blockers: `insufficient-shadow-observation-history`

## Caveats

- BSEO live is not currently eligible. Max promotable committed mode is `bseo-shadow`. Live blockers: insufficient-shadow-observation-history.

## Missing Data

- No missing benchmark inputs were detected.

## Artifact Provenance

- `model_info`: `artifacts/trained_models/latest/model_info.json`
- `eval_report`: `artifacts/eval_runs/build-20260406042818.json`
- `simulation`: `artifacts/eval_runs/build-20260406042818-simulation.json`
- `bseo_report`: `artifacts/eval_runs/build-20260406042818-bseo-report.json`
- `mutation_atlas`: `artifacts/eval_runs/build-20260406042818-mutation-bias-atlas.json`
- `lineage`: `artifacts/eval_runs/build-20260406042818-bseo-lineage.json`
- `drift_report`: `artifacts/drift_reports/build-20260406042818.json`
- `runtime_policy`: `configs/thresholds/runtime-policy.json`
- `thresholds`: `configs/thresholds/default.json`
- `bseo_policy`: `configs/thresholds/bseo-policy.json`
- `runtime_governance`: `artifacts/reports/runtime-governance-latest.json`
