# TruthLens Benchmarks

This directory is the GitHub-facing benchmark surface for the committed TruthLens artifacts.

Rules:

- Benchmark claims in `README.md` must trace back to `docs/benchmarks/latest/benchmark_summary.json`.
- Visuals in `docs/benchmarks/latest/assets/` are generated from committed artifacts only.
- Missing BSEO lineage, atlas, or policy artifacts must produce stubs and caveats rather than fabricated charts.
- Small sample sizes, validation regressions, and runtime-policy mismatches must be surfaced explicitly.

Primary outputs:

- `latest/benchmark_summary.json`
- `latest/benchmark_summary.md`
- `latest/assets/*.svg`
- `latest/assets/overall_metrics_table.md`
- `latest/interactive/*.html`

Regenerate everything with:

```powershell
pnpm docs:render-benchmarks
```

Current committed caveat:

- The present root-artifact benchmark is a tiny-sample snapshot. Treat it as repository truth for the committed artifacts, not as a production performance claim.
