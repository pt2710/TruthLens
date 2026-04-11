# Benchmark Summary

- Generated at: `2026-04-11T06:25:42.313810+00:00`
- Build ID: `build-20260411062330`
- Model version: `baseline-v1-build-20260411062330`
- Eval sample count: `44`
- Configured runtime policy mode: `bseo-shadow`
- Resolved runtime policy mode: `bseo-shadow`
- Governance recommended mode: `bseo-shadow`
- Max promotable mode: `bseo-live`

## Metrics

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 1.000 | 1.000 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 1.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.220 | 0.220 |

## Observation And Feedback Intake

- Browser observations: `1459`
- Unique observed items: `671`
- Observation rows linked back to scored items: `1459`
- Supplemental candidates: `0`
- Split-blocked candidates: `0`
- Supplemental adjudicated: `0`

## Runtime Governance

- Shadow eligible: `True`
- Live eligible: `True`
- Shadow observation count: `911`
- BSEO objective score: `0.8344`

## Caveats

- No supplemental browser/feedback candidates are currently committed, so intake charts should be read as capability hooks rather than mature operational volume.
- No committed collection-scoped review artifacts are present yet, so mix/playlist batch handling is implemented but not benchmark-rich in the repo snapshot.

## Missing Data

- No missing benchmark inputs were detected.

## Artifact Provenance

- `model_info`: `artifacts/trained_models/latest/model_info.json`
- `eval_report`: `artifacts/eval_runs/build-20260411062330.json`
- `simulation`: `artifacts/eval_runs/build-20260411062330-simulation.json`
- `bseo_report`: `artifacts/eval_runs/build-20260411062330-bseo-report.json`
- `mutation_atlas`: `artifacts/eval_runs/build-20260411062330-mutation-bias-atlas.json`
- `lineage`: `artifacts/eval_runs/build-20260411062330-bseo-lineage.json`
- `drift_report`: `artifacts/drift_reports/build-20260411062330.json`
- `runtime_policy`: `configs/thresholds/runtime-policy.json`
- `thresholds`: `configs/thresholds/default.json`
- `bseo_policy`: `configs/thresholds/bseo-policy.json`
- `runtime_governance`: `artifacts/reports/runtime-governance-latest.json`
- `supplemental_candidates`: `missing`
- `supplemental_adjudication`: `missing`
- `supplemental_gold`: `missing`
