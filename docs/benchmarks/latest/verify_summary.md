# TruthLens Verify Summary

- Generated at: `2026-04-25T17:15:17.388287+00:00`
- Overall status: `passed`
- Commands passed: `9/9`
- Total duration (s): `255.638`

## Benchmark Context

- Build ID: `build-20260425085620`
- Model version: `baseline-v1-build-20260425085620`
- Eval sample count: `101`
- Configured runtime mode: `bseo-live`
- Resolved runtime mode: `bseo-live`
- Recommended runtime mode: `bseo-live`

## Command Table

| Command | Status | Exit code | Duration (s) |
| --- | --- | ---: | ---: |
| `pytest` | `passed` | 0 | 92.47 |
| `ruff` | `passed` | 0 | 0.187 |
| `mypy` | `passed` | 0 | 65.44 |
| `pnpm-typecheck` | `passed` | 0 | 9.405 |
| `pnpm-test` | `passed` | 0 | 15.358 |
| `pnpm-build` | `passed` | 0 | 8.707 |
| `docs-render-architecture` | `passed` | 0 | 10.074 |
| `docs-render-benchmarks` | `passed` | 0 | 13.823 |
| `pnpm-test-e2e` | `passed` | 0 | 40.174 |

## Output Excerpts

### `pytest`

Command: `C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\.venv\Scripts\python.exe -m pytest -q`

```text
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 89.81s (0:01:29)
```

### `ruff`

Command: `C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\.venv\Scripts\python.exe -m ruff check .`

```text
All checks passed!
```

### `mypy`

Command: `C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\.venv\Scripts\python.exe -m mypy .`

```text
Success: no issues found in 69 source files
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

 [32m✓[39m src/index.test.ts [2m([22m[2m6 tests[22m[2m)[22m[32m 7[2mms[22m[39m

[2m Test Files [22m [1m[32m1 passed[39m[22m[90m (1)[39m
[2m      Tests [22m [1m[32m6 passed[39m[22m[90m (6)[39m
[2m   Start at [22m 19:13:50
[2m   Duration [22m 560ms[2m (transform 92ms, setup 0ms, collect 124ms, tests 7ms, environment 0ms, prepare 149ms)[22m


> @truthlens/extension@0.1.0 test C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\extension
> vitest run


[1m[46m RUN [49m[22m [36mv3.2.4 [39m[90mC:/Users/PT-Xb/Desktop/Arbejde_og_Udvikling_af_Machine_learning_og_software/TruthLens/apps/extension[39m

 [32m✓[39m src/overlay/store.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 10[2mms[22m[39m
[90mstdout[2m | src/lib/api.test.ts[2m > [22m[2mscoreFeedItem[2m > [22m[2mfalls back to bootstrap batch scoring when the API hangs
[22m[39m[truthlens:homepage] bootstrap fallback used for /batch-score {
  itemCount: [33m1[39m,
  reason: [32m'TruthLens API request timed out after 12000ms.'[39m
}

[90mstdout[2m | src/lib/api.test.ts[2m > [22m[2mscoreFeedItem[2m > [22m[2mfalls back to bootstrap scoring when the API is unavailable
[22m[39m[truthlens:homepage] bootstrap fallback used for /score-item { itemId: [32m'card-2'[39m, reason: [32m'offline'[39m }

[90mstdout[2m | src/lib/api.test.ts[2m > [22m[2mscoreFeedItem[2m > [22m[2mfalls back to bootstrap batch scoring when the API is unavailable
[22m[39m[truthlens:homepage] bootstrap fallback used for /batch-score { itemCount: [33m2[39m, reason: [32m'offline'[39m }

[90mstdout[2m | src/lib/api.test.ts[2m > [22m[2mscoreFeedItem[2m > [22m[2mdoes not cache bootstrap fallback after a batch timeout
[22m[39m[truthlens:homepage] bootstrap fallback used for /batch-score {
  itemCount: [33m1[39m,
  reason: [32m'TruthLens API request timed out after 12000ms.'[39m
}

 [32m✓[39m src/lib/api.test.ts [2m([22m[2m16 tests[22m[2m)[22m[32m 40[2mms[22m[39m
 [32m✓[39m src/lib/userPreferences.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 9[2mms[22m[39m
 [32m✓[39m src/lib/domMutationFilter.test.ts [2m([22m[2m3 tests[22m[2m)[22m[32m 45[2mms[22m[39m
 [32m✓[39m src/background.test.ts [2m([22m[2m5 tests[22m[2m)[22m[32m 20[2mms[22m[39m
 [32m✓[39m src/lib/mockScore.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 10[2mms[22m[39m
 [32m✓[39m src/lib/reviewPrompts.test.ts [2m([22m[2m5 tests[22m[2m)[22m[32m 8[2mms[22m[39m
 [32m✓[39m src/lib/personalization.test.ts [2m([22m[2m3 tests[22m[2m)[22m[32m 6[2mms[22m[39m
 [32m✓[39m src/overlay/App.test.tsx [2m([22m[2m7 tests[22m[2m)[22m[33m 581[2mms[22m[39m
 [32m✓[39m src/lib/feedReranking.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 8[2mms[22m[39m
 [32m✓[39m src/lib/youtubeWatchMetadata.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 9[2mms[22m[39m
 [32m✓[39m src/lib/sessionStats.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 10[2mms[22m[39m
 [32m✓[39m src/lib/reportFeedbackScoring.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 5[2mms[22m[39m
 [32m✓[39m src/lib/channelTrustCache.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 5[2mms[22m[39m
 [32m✓[39m src/lib/feedRerankSettings.test.ts [2m([22m[2m2 tests[22m[2m)[22m[32m 6[2mms[22m[39m
 [32m✓[39m src/lib/feedSco
... [truncated]
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
[32m✓[39m 45 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mpopup.html               [39m[1m[2m  0.39 kB[22m[1m[22m[2m │ gzip:  0.26 kB[22m
[2mdist/[22m[36mbackground.js            [39m[1m[2m  2.60 kB[22m[1m[22m[2m │ gzip:  1.16 kB[22m
[2mdist/[22m[36mchunks/runtimeConfig.js  [39m[1m[2m 68.71 kB[22m[1m[22m[2m │ gzip: 15.61 kB[22m
[2mdist/[22m[36mpopup.js                 [39m[1m[2m204.16 kB[22m[1m[22m[2m │ gzip: 63.41 kB[22m
[32m✓ built in 1.10s[39m
[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 61 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[35massets/content.css  [39m[1m[2m  7.12 kB[22m[1m[22m[2m │ gzip:   1.87 kB[22m
[2mdist/[22m[36mcontent.js          [39m[1m[2m359.86 kB[22m[1m[22m[2m │ gzip: 105.64 kB[22m
[32m✓ built in 1.29s[39m
Extension build verified.

> @truthlens/labeling-ui@0.1.0 build C:\Users\PT-Xb\Desktop\Arbejde_og_Udvikling_af_Machine_learning_og_software\TruthLens\apps\labeling-ui
> vite build

[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 41 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mindex.html                  [39m[1m[2m  0.42 kB[22m[1m[22m[2m │ gzip:  0.28 kB[22m
[2mdist/[22m[32mannotation-batch.data.json  [39m[1m[2m287.13 kB[22m[1m[22m[2m │ gzip: 11.64 kB[22m
[2mdist/[22m[35massets/index-KaTrgatk.css   [39m[1m[2m  3.61 kB[22m[1m[22m[2m │ gzip:  1.15 kB[22m
[2mdist/[22m[36massets/index-6lzYeW9X.js    [39m[1m[2m277.95 kB[22m[1m[22m[2m │ gzip: 79.74 kB[22m
[32m✓ built in 1.09s[39m
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
  "generated_at": "2026-04-25T17:14:36.225812+00:00",
  "build_id": "build-20260425085620",
  "model_version": "baseline-v1-build-20260425085620",
  "trained_at": "2026-04-25T08:56:20.686458+00:00",
  "sample_count": 101,
  "artifact_paths": {
    "model_info": "artifacts/trained_models/latest/model_info.json",
    "eval_report": "artifacts/eval_runs/build-20260425085620.json",
    "simulation": "artifacts/eval_runs/build-20260425085620-simulation.json",
    "training_history": "artifacts/eval_runs/build-20260425085620-training-history.json",
    "bseo_report": "artifacts/eval_runs/build-20260425085620-bseo-report.json",
    "mutation_atlas": "artifacts/eval_runs/build-20260425085620-mutation-bias-atlas.json",
    "lineage": "artifacts/eval_runs/build-20260425085620-bseo-lineage.json",
    "drift_report": "artifacts/drift_reports/build-20260425085620.json",
    "runtime_policy": "configs/thresholds/runtime-policy.json",
    "thresholds": "configs/thresholds/default.json",
    "bseo_policy": "configs/thresholds/bseo-policy.json",
    "runtime_governance": "artifacts/reports/runtime-governance-latest.json",
    "supplemental_candidates": null,
    "supplemental_adjudication": null,
    "supplemental_gold": null,
    "operator_feedback_manifest": "datasets/manifests/operator_feedback/latest.json",
    "operator_ingestion_manifest": "datasets/manifests/operator_feedback/build-20260425085620-ingestion.json",
    "operator_adjudication": "datasets/manifests/operator_feedback/adjudication/discovery-20260425085618-operator-feedback.json",
    "operator_gold": "datasets/manifests/operator_feedback/gold/discovery-20260425085618-operator-feedback.jsonl",
    "build_manifest": "datasets/manifests/builds/latest.json"
  },
  "artifact_timestamps": {
    "model_info": "2026-04-25T09:01:47.857107+00:00",
    "eval_report": "2026-04-25T09:01:47.857107+00:00",
    "simulation": "2026-04-25T09:02:24.749063+00:00",
    "training_history": "2026-04-25T09:01:47.857107+00:00",
    "bseo_report": "2026-04-25T09:02:24.751071+00:00",
    "mutation_atlas": "2026-04-25T09:02:24.771651+00:00",
    "lineage": "2026-04-25T09:02:24.769642+00:00",
    "drift_report": "2026-04-25T09:02:24.771651+00:00",
    "runtime_policy": "2026-04-23T17:16:04.310801+00:00",
    "thresholds": "2026-04-25T09:02:24.773667+00:00",
    "bseo_policy": "2026-04-25T09:02:24.775678+00:00",
    "runtime_governance": "2026-04-25T17:14:35.948167+00:00",
    "supplemental_candidates": null,
    "supplemental_adjudication": null,
    "supplemental_gold": null,
    "operator_feedback_manifest": "2026-04-25T08:56:20.303763+00:00",
    "operator_ingestion_manifest": "2026-04-25T08:56:20.586240+00:00",
    "operator_adjudication": "2026-04-25T08:56:20.336170+00:00",
    "operator_gold": "2026-04-25T08:56:20.339904+00:00",
    "build_manifest": "2026-04-25T08:56:20.703349+00:00"
  },
  "runtime_truth": {
    "configured_policy_mode": "bseo-live",
    "resolved_policy_mode": "bseo-live",
    "bseo_artifact_committed": true,
    "bseo_artifact_compatible": true,
    "selective_verification_contract_present": true,
    "heavy_llm_hot_path": false,
    "recommended_policy_mode": "bseo-live",
    "max_promotable_mode": "bseo-live",
    "shadow_eligible": true,
    "live_eligible": true
  },
  "runtime_governance": {
    "generated_at": "2026-04-25T17:14:35.931286+00:00",
    "build_id": "build-20260425085620",
    "runtime_policy": {
      "configured_mode": "bseo-live",
      "resolved_mode": "bseo-live",
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
        "age_hours": 8.304,
        "build_id": "build-20260425085620",
        "policy_version": "bseo-control-policy-v1"
      },
      "lineage_count": 125,
      "mutation_atlas_status": "clustere
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
[32m✓[39m 45 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mpopup.html               [39m[1m[2m  0.39 kB[22m[1m[22m[2m │ gzip:  0.26 kB[22m
[2mdist/[22m[36mbackground.js            [39m[1m[2m  2.60 kB[22m[1m[22m[2m │ gzip:  1.16 kB[22m
[2mdist/[22m[36mchunks/runtimeConfig.js  [39m[1m[2m 68.71 kB[22m[1m[22m[2m │ gzip: 15.61 kB[22m
[2mdist/[22m[36mpopup.js                 [39m[1m[2m204.16 kB[22m[1m[22m[2m │ gzip: 63.41 kB[22m
[32m✓ built in 1.11s[39m
[36mvite v6.4.1 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 61 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[35massets/content.css  [39m[1m[2m  7.12 kB[22m[1m[22m[2m │ gzip:   1.87 kB[22m
[2mdist/[22m[36mcontent.js          [39m[1m[2m359.86 kB[22m[1m[22m[2m │ gzip: 105.64 kB[22m
[32m✓ built in 1.35s[39m
Extension build verified.
{
  "batchRequests": 6,
  "browserObservations": 11,
  "feedbackEvents": 1,
  "optimizationRequests": 1,
  "overlayRoots": 1,
  "processedCards": 3
}
```
