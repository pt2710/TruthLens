# TruthLens Verify Summary

- Generated at: `2026-04-10T20:15:48.759615+00:00`
- Overall status: `passed`
- Commands passed: `9/9`
- Total duration (s): `91.285`

## Benchmark Context

- Build ID: `build-20260406042818`
- Model version: `baseline-v1-build-20260406042818`
- Eval sample count: `44`
- Configured runtime mode: `bseo-shadow`
- Resolved runtime mode: `bseo-shadow`
- Recommended runtime mode: `bseo-shadow`

## Command Table

| Command | Status | Exit code | Duration (s) |
| --- | --- | ---: | ---: |
| `pytest` | `passed` | 0 | 47.315 |
| `ruff` | `passed` | 0 | 0.15 |
| `mypy` | `passed` | 0 | 0.987 |
| `pnpm-typecheck` | `passed` | 0 | 9.083 |
| `pnpm-test` | `passed` | 0 | 7.785 |
| `pnpm-build` | `passed` | 0 | 8.924 |
| `docs-render-architecture` | `passed` | 0 | 5.072 |
| `docs-render-benchmarks` | `passed` | 0 | 3.093 |
| `pnpm-test-e2e` | `passed` | 0 | 8.876 |

## Output Excerpts

### `pytest`

Command: `C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\.venv\Scripts\python.exe -m pytest -q`

```text
........................................................................ [ 66%]
....................................                                     [100%]
108 passed in 45.88s
```

### `ruff`

Command: `C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\.venv\Scripts\python.exe -m ruff check .`

```text
All checks passed!
```

### `mypy`

Command: `C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\.venv\Scripts\python.exe -m mypy .`

```text
Success: no issues found in 64 source files
```

### `pnpm-typecheck`

Command: `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command pnpm typecheck`

```text
> truthlens@0.1.0 typecheck C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens
> pnpm --filter @truthlens/shared-schemas typecheck && pnpm --filter @truthlens/extension typecheck && pnpm --filter @truthlens/labeling-ui typecheck


> @truthlens/shared-schemas@0.1.0 typecheck C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\libs\shared-schemas
> tsc --noEmit -p tsconfig.json


> @truthlens/extension@0.1.0 typecheck C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\extension
> tsc --noEmit -p tsconfig.json


> @truthlens/labeling-ui@0.1.0 typecheck C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\labeling-ui
> tsc --noEmit -p tsconfig.json
```

### `pnpm-test`

Command: `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command pnpm test`

```text
> truthlens@0.1.0 test C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens
> pnpm --filter @truthlens/shared-schemas test && pnpm --filter @truthlens/extension test && pnpm --filter @truthlens/labeling-ui test


> @truthlens/shared-schemas@0.1.0 test C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\libs\shared-schemas
> vitest run


[1m[46m RUN [49m[22m [36mv3.2.4 [39m[90mC:/Users/PT-Xb/Desktop/Arbejde_og_Udvikling_af_Machine_learning_og_software/TruthLens/libs/shared-schemas[39m

 [32m✓[39m src/index.test.ts [2m([22m[2m6 tests[22m[2m)[22m[32m 8[2mms[22m[39m

[2m Test Files [22m [1m[32m1 passed[39m[22m[90m (1)[39m
[2m      Tests [22m [1m[32m6 passed[39m[22m[90m (6)[39m
[2m   Start at [22m 22:15:16
[2m   Duration [22m 576ms[2m (transform 98ms, setup 0ms, collect 126ms, tests 8ms, environment 0ms, prepare 160ms)[22m


> @truthlens/extension@0.1.0 test C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\extension
> vitest run


[1m[46m RUN [49m[22m [36mv3.2.4 [39m[90mC:/Users/PT-Xb/Desktop/Arbejde_og_Udvikling_af_Machine_learning_og_software/TruthLens/apps/extension[39m

 [32m✓[39m src/lib/mockScore.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 9[2mms[22m[39m
 [32m✓[39m src/lib/api.test.ts [2m([22m[2m8 tests[22m[2m)[22m[32m 18[2mms[22m[39m
 [32m✓[39m src/lib/personalization.test.ts [2m([22m[2m3 tests[22m[2m)[22m[32m 8[2mms[22m[39m
 [32m✓[39m src/overlay/store.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 9[2mms[22m[39m
 [32m✓[39m src/lib/domMutationFilter.test.ts [2m([22m[2m3 tests[22m[2m)[22m[32m 53[2mms[22m[39m
 [32m✓[39m src/lib/userPreferences.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 5[2mms[22m[39m
 [32m✓[39m src/lib/reviewPrompts.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 8[2mms[22m[39m
 [32m✓[39m src/lib/sessionStats.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 11[2mms[22m[39m
 [32m✓[39m src/lib/youtubeWatchMetadata.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 6[2mms[22m[39m
 [32m✓[39m src/background.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 4[2mms[22m[39m
 [32m✓[39m src/overlay/App.test.tsx [2m([22m[2m4 tests[22m[2m)[22m[33m 370[2mms[22m[39m

[2m Test Files [22m [1m[32m11 passed[39m[22m[90m (11)[39m
[2m      Tests [22m [1m[32m34 passed[39m[22m[90m (34)[39m
[2m   Start at [22m 22:15:18
[2m   Duration [22m 2.38s[2m (transform 510ms, setup 0ms, collect 1.19s, tests 502ms, environment 3.48s, prepare 2.22s)[22m


> @truthlens/labeling-ui@0.1.0 test C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\labeling-ui
> vitest run


[1m[46m RUN [49m[22m [36mv3.2.4 [39m[90mC:/Users/PT-Xb/Desktop/Arbejde_og_Udvikling_af_Machine_learning_og_software/TruthLens/apps/labeling-ui[39m

 [32m✓[39m src/lib/annotationBatch.test.ts [2m([22m[2m1 test[22m[2m)[22m[32m 7[2mms[22m[39m

[2m Test Files [22m [1m[32m1 passed[39m[22m[90m (1)[39m
[2m      Tests [22m [1m[32m1 passed[39m[22m[90m (1)[39m
[2m   Start at [22m 22:15:21
[2m   Duration [22m 586ms[2m (transform 101ms, setup 0ms, collect 137ms, tests 7ms, environment 0ms, prepare 153ms)[22m
```

### `pnpm-build`

Command: `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command pnpm build`

```text
> truthlens@0.1.0 build C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens
> pnpm --filter @truthlens/shared-schemas build && pnpm --filter @truthlens/extension build && pnpm --filter @truthlens/labeling-ui build


> @truthlens/shared-schemas@0.1.0 build C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\libs\shared-schemas
> tsc -p tsconfig.json


> @truthlens/extension@0.1.0 build C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\extension
> vite build && vite build --config vite.content.config.ts && node scripts/verify-build.mjs

[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 42 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mpopup.html     [39m[1m[2m  0.32 kB[22m[1m[22m[2m │ gzip:  0.22 kB[22m
[2mdist/[22m[36mbackground.js  [39m[1m[2m  1.76 kB[22m[1m[22m[2m │ gzip:  0.86 kB[22m
[2mdist/[22m[36mpopup.js       [39m[1m[2m271.33 kB[22m[1m[22m[2m │ gzip: 78.22 kB[22m
[32m✓ built in 1.13s[39m
[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 51 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[35massets/content.css  [39m[1m[2m  7.07 kB[22m[1m[22m[2m │ gzip:  1.86 kB[22m
[2mdist/[22m[36mcontent.js          [39m[1m[2m332.41 kB[22m[1m[22m[2m │ gzip: 96.77 kB[22m
[32m✓ built in 1.28s[39m
Extension build verified.

> @truthlens/labeling-ui@0.1.0 build C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\labeling-ui
> vite build

[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 41 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mindex.html                  [39m[1m[2m  0.42 kB[22m[1m[22m[2m │ gzip:  0.28 kB[22m
[2mdist/[22m[32mannotation-batch.data.json  [39m[1m[2m160.61 kB[22m[1m[22m[2m │ gzip:  6.65 kB[22m
[2mdist/[22m[35massets/index-KaTrgatk.css   [39m[1m[2m  3.61 kB[22m[1m[22m[2m │ gzip:  1.15 kB[22m
[2mdist/[22m[36massets/index-DqmK03-V.js    [39m[1m[2m277.76 kB[22m[1m[22m[2m │ gzip: 79.68 kB[22m
[32m✓ built in 1.21s[39m
```

### `docs-render-architecture`

Command: `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command pnpm docs:render-architecture`

```text
> truthlens@0.1.0 docs:render-architecture C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens
> node scripts/render_architecture_diagram.mjs
```

### `docs-render-benchmarks`

Command: `C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\.venv\Scripts\python.exe scripts/render_benchmark_visualizations.py`

```text
{
  "generated_at": "2026-04-10T20:15:39.600347+00:00",
  "build_id": "build-20260406042818",
  "model_version": "baseline-v1-build-20260406042818",
  "trained_at": "2026-04-06T04:28:18.606357+00:00",
  "sample_count": 44,
  "artifact_paths": {
    "model_info": "artifacts/trained_models/latest/model_info.json",
    "eval_report": "artifacts/eval_runs/build-20260406042818.json",
    "simulation": "artifacts/eval_runs/build-20260406042818-simulation.json",
    "bseo_report": "artifacts/eval_runs/build-20260406042818-bseo-report.json",
    "mutation_atlas": "artifacts/eval_runs/build-20260406042818-mutation-bias-atlas.json",
    "lineage": "artifacts/eval_runs/build-20260406042818-bseo-lineage.json",
    "drift_report": "artifacts/drift_reports/build-20260406042818.json",
    "runtime_policy": "configs/thresholds/runtime-policy.json",
    "thresholds": "configs/thresholds/default.json",
    "bseo_policy": "configs/thresholds/bseo-policy.json",
    "runtime_governance": "artifacts/reports/runtime-governance-latest.json",
    "supplemental_candidates": null,
    "supplemental_adjudication": null,
    "supplemental_gold": null
  },
  "artifact_timestamps": {
    "model_info": "2026-04-06T04:28:26.682182+00:00",
    "eval_report": "2026-04-06T04:28:26.684195+00:00",
    "simulation": "2026-04-06T04:28:51.362790+00:00",
    "bseo_report": "2026-04-06T04:28:51.365789+00:00",
    "mutation_atlas": "2026-04-06T04:28:51.393782+00:00",
    "lineage": "2026-04-06T04:28:51.393782+00:00",
    "drift_report": "2026-04-06T04:28:51.395790+00:00",
    "runtime_policy": "2026-04-06T04:40:02.540092+00:00",
    "thresholds": "2026-04-06T04:28:51.397798+00:00",
    "bseo_policy": "2026-04-06T04:28:51.402820+00:00",
    "runtime_governance": "2026-04-10T20:15:39.550807+00:00",
    "supplemental_candidates": null,
    "supplemental_adjudication": null,
    "supplemental_gold": null
  },
  "runtime_truth": {
    "configured_policy_mode": "bseo-shadow",
    "resolved_policy_mode": "bseo-shadow",
    "bseo_artifact_committed": true,
    "bseo_artifact_compatible": true,
    "selective_verification_contract_present": true,
    "heavy_llm_hot_path": false,
    "recommended_policy_mode": "bseo-shadow",
    "max_promotable_mode": "bseo-live",
    "shadow_eligible": true,
    "live_eligible": true
  },
  "runtime_governance": {
    "generated_at": "2026-04-10T20:15:39.550806+00:00",
    "build_id": "build-20260406042818",
    "runtime_policy": {
      "configured_mode": "bseo-shadow",
      "resolved_mode": "bseo-shadow",
      "bseo_min_confidence": 0.58,
      "bseo_max_uncertainty": 0.45,
      "bseo_artifact_max_age_hours": 168.0
    },
    "artifacts": {
      "bseo_policy": {
        "available": true,
        "compatible": true,
        "stale": false,
        "status": "compatible",
        "reason": null,
        "age_hours": 111.789,
        "build_id": "build-20260406042818",
        "policy_version": "bseo-control-policy-v1"
      },
      "lineage_count": 125,
      "mutation_atlas_status": "clustered",
      "usable_mutations": 106
    },
    "dataset": {
      "train_count": 110,
      "validation_count": 44,
      "test_count": 44,
      "eval_sample_count": 44
    },
    "performance": {
      "eval_f1": 1.0,
      "validation_f1": 1.0,
      "validation_gap": 0.0,
      "calibration_error": 0.2201,
      "bseo_objective_score": 0.8344,
      "benign_false_positive_rate": 0.0,
      "shadow_observation_count": 643
    },
    "promotion": {
      "shadow_eligible": true,
      "shadow_blockers": [],
      "live_eligible": true,
      "live_blockers": [],
      "recommended_mode": "bseo-shadow",
      "max_promotable_mode": "bseo-live"
    }
  },
  "metrics": {
    "eval": {
      "precision": 1.0,
      "recall": 1.0,
      "f1": 1.0,
      "positive_rate": 0.6364,
      "false_positive_rate": 0.0,
      "false_negative_rate": 0.0,
      "roc_auc": 1.0,
      "pr_auc": 1.0
    },
    "validation": {
      "precision": 1.0,
      "recall": 1.0,
... [truncated]
```

### `pnpm-test-e2e`

Command: `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command pnpm test:e2e`

```text
> truthlens@0.1.0 test:e2e C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens
> pnpm --filter @truthlens/extension build && node tests/e2e/extension-fixture.mjs


> @truthlens/extension@0.1.0 build C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\extension
> vite build && vite build --config vite.content.config.ts && node scripts/verify-build.mjs

[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 42 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mpopup.html     [39m[1m[2m  0.32 kB[22m[1m[22m[2m │ gzip:  0.22 kB[22m
[2mdist/[22m[36mbackground.js  [39m[1m[2m  1.76 kB[22m[1m[22m[2m │ gzip:  0.86 kB[22m
[2mdist/[22m[36mpopup.js       [39m[1m[2m271.33 kB[22m[1m[22m[2m │ gzip: 78.22 kB[22m
[32m✓ built in 1.13s[39m
[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 51 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[35massets/content.css  [39m[1m[2m  7.07 kB[22m[1m[22m[2m │ gzip:  1.86 kB[22m
[2mdist/[22m[36mcontent.js          [39m[1m[2m332.41 kB[22m[1m[22m[2m │ gzip: 96.77 kB[22m
[32m✓ built in 1.36s[39m
Extension build verified.
{
  "batchRequests": 3,
  "browserObservations": 5,
  "feedbackEvents": 1,
  "optimizationRequests": 1,
  "overlayRoots": 1,
  "processedCards": 4
}
```
