# TruthLens Benchmarks

This directory is the GitHub-facing benchmark surface for the committed TruthLens artifacts.

Rules:

- Benchmark claims in `README.md` must trace back to `docs/benchmarks/latest/benchmark_summary.json`.
- Visuals in `docs/benchmarks/latest/assets/` are generated from committed artifacts only.
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
- `latest/interactive/*.html`
- `../../artifacts/reports/runtime-governance-latest.json`

Regenerate everything with:

```powershell
pnpm runtime:promote-auto
pnpm docs:render-benchmarks
pnpm docs:render-verify
```

Current committed caveat:

- The present root-artifact benchmark reflects a materially larger sample than the previous tiny-sample snapshot, but it is still a repository benchmark rather than a production claim.
- `bseo-shadow` is committed and promoted.
- current governance artifacts may mark `bseo-live` as eligible before the repo actually promotes it; docs must distinguish eligibility from the committed active runtime mode.
