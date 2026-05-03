# TruthLens Benchmarks

This directory is the GitHub-facing benchmark surface for the committed TruthLens artifacts.

Rules:

- Benchmark claims in `README.md` must trace back to `docs/benchmarks/latest/benchmark_summary.json`.
- Visuals in `docs/benchmarks/latest/assets/` are generated from committed artifacts only.
- The public repo keeps curated benchmark truth surfaces and metadata, not every raw eval/drift payload or binary model bundle.
- Adaptive Semantic Evidence Routing refreshes must include route-aware eval and calibration decision artifacts before README claims change.
- Creative false-positive calibration changes must include a route-aware before/after diagnostic artifact before benchmark claims change.
- Missing BSEO lineage, atlas, or policy artifacts must produce stubs and caveats rather than fabricated charts.
- Small sample sizes, validation regressions, runtime-governance blockers, and runtime-policy mismatches must be surfaced explicitly.
- Browser-observation and supplemental-intake volume must be surfaced honestly; zero supplemental volume is a valid committed state.
- Collection-scope review/report support may be committed before collection-batch artifact volume exists; zero committed collection intake must be called out rather than hidden.
- `blur` may remain an internal action label, but GitHub-facing docs and visuals must describe the current extension behavior truthfully as a visible warning-state rather than a forced visual blur.

Primary outputs:

- `latest/benchmark_summary.json`
- `latest/benchmark_summary.md`
- `latest/verify_summary.json`
- `latest/verify_summary.md`
- `latest/assets/*.svg`
- `latest/assets/observation_feedback_intake.svg`
- `latest/assets/overall_metrics_table.md`
- `latest/assets/semantic_route_distribution.svg`
- `latest/assets/semantic_route_performance.svg`
- `latest/assets/semantic_route_before_after.svg`
- `latest/assets/creative_fpr_diagnostic.svg`
- `latest/interactive/*.html`
- `latest/interactive/semantic_routing_dashboard.html`
- `../../artifacts/reports/runtime-governance-latest.json`

Regenerate everything with:

```powershell
python scripts/benchmark_freshness_gate.py
pnpm runtime:promote-auto
pnpm docs:render-benchmarks
pnpm docs:render-verify
```

Benchmark gate:

- `python scripts/benchmark_freshness_gate.py` is the explicit freshness gate for committed creator/operator benchmark truth.
- If newer committed operator manifests, adjudication records, gold rows, or build truth exist than the current benchmark summary references, the gate must fail and retraining / validation / evaluation / docs refresh are required.
- If no newer committed creator/operator benchmark truth exists, the gate passes as an explicit no-op and the current benchmark surface remains the committed truth.

Current committed caveat:

- The present root-artifact benchmark reflects a materially larger sample than the previous tiny-sample snapshot, but it is still a repository benchmark rather than a production claim.
- `bseo-live` is now committed and promoted because the live guardrails clear on the current root artifacts.
- docs must still distinguish the committed active runtime mode from future eligibility states whenever the runtime policy changes again.
