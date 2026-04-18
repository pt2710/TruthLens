# Benchmark Summary

- Generated at: `2026-04-18T21:18:11.264435+00:00`
- Build ID: `build-20260411064344`
- Model version: `baseline-v1-build-20260411064344`
- Eval sample count: `76`
- Configured runtime policy mode: `threshold-default`
- Resolved runtime policy mode: `threshold-default`
- Governance recommended mode: `threshold-default`
- Max promotable mode: `threshold-default`

## Metrics

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 1.000 | 1.000 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 1.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.142 | 0.147 |

## Observation And Feedback Intake

- Browser observations: `1459`
- Unique observed items: `671`
- Observation rows linked back to scored items: `1459`
- Supplemental candidates: `0`
- Split-blocked candidates: `0`
- Supplemental adjudicated: `0`

## Runtime Governance

- Shadow eligible: `False`
- Live eligible: `False`
- Shadow observation count: `911`
- BSEO objective score: `0.6129`
- Shadow blockers: `stale-bseo-artifact, low-bseo-objective`
- Live blockers: `stale-bseo-artifact, low-bseo-objective, benign-fpr-too-high`

## Caveats

- No supplemental browser/feedback candidates are currently committed, so intake charts should be read as capability hooks rather than mature operational volume.
- No committed collection-scoped review artifacts are present yet, so mix/playlist batch handling is implemented but not benchmark-rich in the repo snapshot.
- BSEO live is not currently eligible. Max promotable committed mode is `threshold-default`. Live blockers: stale-bseo-artifact, low-bseo-objective, benign-fpr-too-high.

## Missing Data

- No missing benchmark inputs were detected.

## Artifact Provenance

- `model_info`: `artifacts/trained_models/latest/model_info.json`
- `eval_report`: `artifacts/eval_runs/build-20260411064344.json`
- `simulation`: `artifacts/eval_runs/build-20260411064344-simulation.json`
- `training_history`: `artifacts/eval_runs/build-20260411064344-training-history.json`
- `bseo_report`: `artifacts/eval_runs/build-20260411064344-bseo-report.json`
- `mutation_atlas`: `artifacts/eval_runs/build-20260411064344-mutation-bias-atlas.json`
- `lineage`: `artifacts/eval_runs/build-20260411064344-bseo-lineage.json`
- `drift_report`: `artifacts/drift_reports/build-20260411064344.json`
- `runtime_policy`: `configs/thresholds/runtime-policy.json`
- `thresholds`: `configs/thresholds/default.json`
- `bseo_policy`: `configs/thresholds/bseo-policy.json`
- `runtime_governance`: `artifacts/reports/runtime-governance-latest.json`
- `supplemental_candidates`: `missing`
- `supplemental_adjudication`: `missing`
- `supplemental_gold`: `missing`
