# Benchmark Summary

- Generated at: `2026-04-23T17:19:57.991263+00:00`
- Build ID: `build-20260423171503`
- Model version: `baseline-v1-build-20260423171503`
- Eval sample count: `101`
- Configured runtime policy mode: `bseo-live`
- Resolved runtime policy mode: `bseo-live`
- Governance recommended mode: `bseo-live`
- Max promotable mode: `bseo-live`

## Metrics

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 0.962 | 1.000 |
| Recall | 1.000 | 1.000 |
| F1 | 0.981 | 1.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.176 | 0.187 |

## Observation And Feedback Intake

- Browser observations: `1459`
- Unique observed items: `671`
- Observation rows linked back to scored items: `1459`
- Legacy supplemental candidates: `0`
- Legacy split-blocked candidates: `0`
- Local-user feedback events: `60`
- Creator/operator candidates: `53`
- Creator/operator gold rows: `53`
- Creator/operator ingested rows: `53`
- Global benchmark truth rows: `395`

## Runtime Governance

- Shadow eligible: `True`
- Live eligible: `True`
- Shadow observation count: `911`
- BSEO objective score: `0.8375`

## Caveats

- No committed collection-scoped review artifacts are present yet, so mix/playlist batch handling is implemented but not benchmark-rich in the repo snapshot.

## Missing Data

- No missing benchmark inputs were detected.

## Artifact Provenance

- `model_info`: `artifacts/trained_models/latest/model_info.json`
- `eval_report`: `artifacts/eval_runs/build-20260423171503.json`
- `simulation`: `artifacts/eval_runs/build-20260423171503-simulation.json`
- `training_history`: `artifacts/eval_runs/build-20260423171503-training-history.json`
- `bseo_report`: `artifacts/eval_runs/build-20260423171503-bseo-report.json`
- `mutation_atlas`: `artifacts/eval_runs/build-20260423171503-mutation-bias-atlas.json`
- `lineage`: `artifacts/eval_runs/build-20260423171503-bseo-lineage.json`
- `drift_report`: `artifacts/drift_reports/build-20260423171503.json`
- `runtime_policy`: `configs/thresholds/runtime-policy.json`
- `thresholds`: `configs/thresholds/default.json`
- `bseo_policy`: `configs/thresholds/bseo-policy.json`
- `runtime_governance`: `artifacts/reports/runtime-governance-latest.json`
- `supplemental_candidates`: `missing`
- `supplemental_adjudication`: `missing`
- `supplemental_gold`: `missing`
- `operator_feedback_manifest`: `datasets/manifests/operator_feedback/latest.json`
- `operator_ingestion_manifest`: `datasets/manifests/operator_feedback/build-20260423171503-ingestion.json`
- `operator_adjudication`: `datasets/manifests/operator_feedback/adjudication/discovery-20260423171502-operator-feedback.json`
- `operator_gold`: `datasets/manifests/operator_feedback/gold/discovery-20260423171502-operator-feedback.jsonl`
- `build_manifest`: `datasets/manifests/builds/latest.json`
