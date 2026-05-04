# Benchmark Summary

- Generated at: `2026-05-03T16:03:23.863754+00:00`
- Build ID: `build-20260425085620`
- Model version: `baseline-v1-build-20260425085620`
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
| Calibration error | 0.175 | 0.185 |

## Adaptive Semantic Evidence Routing Eval

- Route-aware eval artifact: `docs/benchmarks/latest/artifacts/build-20260425085620-semantic-routing-eval.json`
- Route-aware baseline artifact: `docs/benchmarks/latest/artifacts/build-20260425085620-semantic-routing-baseline-eval.json`
- Calibration decision artifact: `docs/benchmarks/latest/artifacts/build-20260425085620-calibration-decision.json`
- Creative FPR diagnostic artifact: `docs/benchmarks/latest/artifacts/build-20260425085620-creative-fpr-diagnostic.json`
- Route-aware sample count: `159`
- Creative false-positive rate: `0.0`
- Deceptive/factual camouflage false-negative rate: `0.0`
- BSEO override frequency: `0.4843`
- Calibration decision: `controlled-calibration-recorded`
- Creative FPR gate accepted: `True`
- Creative FPR before/after: `0.5909` -> `0.0`

## Observation And Feedback Intake

- Browser observations: `1459`
- Unique observed items: `671`
- Observation rows linked back to scored items: `1459`
- Legacy supplemental candidates: `0`
- Legacy split-blocked candidates: `0`
- Local-user feedback events: `85`
- Creator/operator candidates: `53`
- Creator/operator gold rows: `53`
- Creator/operator ingested rows: `53`
- Global benchmark truth rows: `395`

## Runtime Governance

- Shadow eligible: `True`
- Live eligible: `True`
- Shadow observation count: `911`
- BSEO objective score: `0.8178`

## Caveats

- No committed collection-scoped review artifacts are present yet, so mix/playlist batch handling is implemented but not benchmark-rich in the repo snapshot.

## Missing Data

- No missing benchmark inputs were detected.

## Artifact Provenance

- `model_info`: `artifacts/trained_models/latest/model_info.json`
- `eval_report`: `docs/benchmarks/latest/artifacts/build-20260425085620.json`
- `simulation`: `docs/benchmarks/latest/artifacts/build-20260425085620-simulation.json`
- `training_history`: `docs/benchmarks/latest/artifacts/build-20260425085620-training-history.json`
- `semantic_routing_eval`: `docs/benchmarks/latest/artifacts/build-20260425085620-semantic-routing-eval.json`
- `semantic_routing_baseline_eval`: `docs/benchmarks/latest/artifacts/build-20260425085620-semantic-routing-baseline-eval.json`
- `calibration_decision`: `docs/benchmarks/latest/artifacts/build-20260425085620-calibration-decision.json`
- `creative_fpr_before_eval`: `docs/benchmarks/latest/artifacts/build-20260425085620-creative-fpr-before-eval.json`
- `creative_fpr_diagnostic`: `docs/benchmarks/latest/artifacts/build-20260425085620-creative-fpr-diagnostic.json`
- `no_retrain_decision`: `missing`
- `no_promotion_decision`: `missing`
- `bseo_report`: `docs/benchmarks/latest/artifacts/build-20260425085620-bseo-report.json`
- `mutation_atlas`: `docs/benchmarks/latest/artifacts/build-20260425085620-mutation-bias-atlas.json`
- `lineage`: `docs/benchmarks/latest/artifacts/build-20260425085620-bseo-lineage.json`
- `drift_report`: `artifacts/drift_reports/build-20260425085620.json`
- `runtime_policy`: `configs/thresholds/runtime-policy.json`
- `thresholds`: `configs/thresholds/default.json`
- `bseo_policy`: `configs/thresholds/bseo-policy.json`
- `runtime_governance`: `artifacts/reports/runtime-governance-latest.json`
- `supplemental_candidates`: `missing`
- `supplemental_adjudication`: `missing`
- `supplemental_gold`: `missing`
- `operator_feedback_manifest`: `datasets/manifests/operator_feedback/latest.json`
- `operator_ingestion_manifest`: `datasets/manifests/operator_feedback/build-20260425085620-ingestion.json`
- `operator_adjudication`: `datasets/manifests/operator_feedback/adjudication/discovery-20260425085618-operator-feedback.json`
- `operator_gold`: `datasets/manifests/operator_feedback/gold/discovery-20260425085618-operator-feedback.jsonl`
- `build_manifest`: `datasets/manifests/builds/latest.json`
