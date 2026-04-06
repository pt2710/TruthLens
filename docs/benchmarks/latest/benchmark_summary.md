# Benchmark Summary

- Generated at: `2026-04-06T04:16:02.789547+00:00`
- Build ID: `build-20260323000612`
- Model version: `baseline-v1-build-20260323000612`
- Eval sample count: `4`
- Configured runtime policy mode: `threshold-default`
- Resolved runtime policy mode: `threshold-default`

## Metrics

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 1.000 | 0.000 |
| Recall | 1.000 | 0.000 |
| F1 | 1.000 | 0.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.000 | 0.000 |

## Caveats

- Committed eval sample count is only 4; metrics are unstable and must not be treated as production benchmarks.
- Validation performance is materially weaker than eval performance; treat the current benchmark as a tiny-sample sanity signal, not a stable generalization claim.
- No committed configs/thresholds/bseo-policy.json is present at repo root, so BSEO shadow/live remains a code-supported mode rather than a promoted committed runtime artifact.
- Committed simulation artifacts do not currently include populated BSEO search outputs, lineage logs, or mutation atlas data.
- Drift report compares against only 4 current rows, so shift readings are directional rather than statistically robust.

## Missing Data

- No missing benchmark inputs were detected.

## Artifact Provenance

- `model_info`: `artifacts/trained_models/latest/model_info.json`
- `eval_report`: `artifacts/eval_runs/build-20260323000612.json`
- `simulation`: `artifacts/eval_runs/build-20260323000612-simulation.json`
- `bseo_report`: `missing`
- `mutation_atlas`: `missing`
- `lineage`: `missing`
- `drift_report`: `artifacts/drift_reports/build-20260323000612.json`
- `runtime_policy`: `configs/thresholds/runtime-policy.json`
- `thresholds`: `configs/thresholds/default.json`
- `bseo_policy`: `missing`
