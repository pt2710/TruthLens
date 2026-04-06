# TruthLens Architecture Revision Diagnosis

Date: 2026-04-06

## 1. Current State Summary

TruthLens already ships a real multimodal runtime with:

- explicit text, vision, metadata, history, anomaly, fusion, and calibration layers
- optional learned paths for text, thumbnail, and temporal history
- a separate policy engine with `threshold-default`, `bseo-shadow`, and `bseo-live`
- explanation generation and human review/report flows
- Android and extension surfaces sharing core score contracts
- trainer, evaluation, BSEO artifact generation, and architecture render tooling

The repo is therefore not greenfield and not structurally broken.

## 2. Confirmed Strengths Already Present

- Core runtime separation between model serving, policy engine, and explanation engine is real.
- Gemini is downstream in manual-report/review support rather than inside the core score classifier.
- BSEO already exists as:
  - interpretation frame inputs
  - search/evaluation artifact output
  - runtime-guarded policy influence
- Artifact guardrails for BSEO live/shadow selection already exist.
- Architecture blueprint tooling and test coverage are already present and working.

## 3. Misalignment vs Target Architecture

### A. Selective deep verification is still implicit, not explicit

Observed:

- `ScoreResult` has no dedicated verification provenance fields.
- `ExplanationEvidence` has no verification evidence kind.
- Runtime heuristics use transcript mismatch and uncertainty, but there is no explicit verification status/trigger/basis contract.

Impact:

- The repo cannot cleanly express `perception -> fusion -> calibration -> selective verification -> policy -> explanation`.
- Review support and verification-oriented reasoning are harder to distinguish from baseline scoring and policy.

### B. Benchmark and visualization truth is under-surfaced

Observed:

- Artifacts exist under `artifacts/trained_models/latest`, `artifacts/eval_runs`, and `artifacts/drift_reports`.
- There is no committed `docs/benchmarks/` pipeline, no benchmark summary generator, and no GitHub-facing benchmark visuals.
- Current artifacts show very small-sample metrics (`sample_count: 4`) and severe validation instability, but README does not surface those caveats.

Impact:

- GitHub-facing repo state does not honestly reflect benchmark quality or artifact provenance.
- There is no reproducible path from raw artifacts to benchmark visuals/tables.

### C. Documentation truth is incomplete

Observed:

- README and ARCHITECTURE already describe BSEO and the hybrid stack correctly at a high level.
- They do not yet define a crisp selective verification layer or benchmark/artifact provenance discipline.
- No diagnosis/reference-architecture document existed before this audit.

Impact:

- Architectural truth is directionally right, but still underspecified where runtime verification and benchmark publication discipline matter most.

### D. Shared schema provenance is too thin

Observed:

- `ScoreResult` exposes risk, confidence, uncertainty, class, bias profile, reasons, and evidence.
- It does not expose:
  - path scores
  - action decision basis
  - verification status / triggers / reasons
  - policy mode provenance
  - artifact build provenance

Impact:

- Clients cannot reliably distinguish core-path evidence from verification-path evidence and policy override provenance.

## 4. Keep / Revise / Remove / Defer Matrix

### Keep

- core multimodal heads
- optional learned paths
- anomaly/VAE sidecar
- history modelling
- BSEO control-genome / lineage / atlas pipeline
- human review and manual reporting flows
- Android + extension surfaces
- architecture render tooling

### Revise

- shared score/explanation contracts to include provenance and verification fields
- runtime flow to make selective verification explicit and fail-soft
- explanation engine to separate path, verification, and policy reasons
- README and architecture docs to surface benchmark truth and runtime boundaries
- benchmark/visualization pipeline and committed docs assets

### Remove

- no major subsystem removal is justified by the audit

### Defer

- always-on heavy semantic verification
- broader operator analytics beyond benchmark/dashboard surfacing
- stronger end-to-end multimodal models beyond current bounded paths

## 5. Required Contract Changes

- Add explicit verification payloads to shared schemas.
- Add action/policy provenance fields to `ScoreResult`.
- Add path-level score summaries with safe defaults.
- Add artifact/build provenance fields where runtime and benchmark payloads surface decisions.
- Add explanation evidence kinds for verification provenance.

## 6. Required Visualization / Benchmark Changes

- Add a reproducible benchmark summary generator driven by committed artifacts.
- Add static GitHub-embeddable visuals for:
  - overall metrics
  - per-head metrics
  - calibration error
  - confusion matrix
  - threshold/policy summary
  - drift summary
  - artifact provenance
- Add BSEO-focused visuals only when real source data exists; otherwise emit clear unavailability stubs.
- Add a benchmark docs root under `docs/benchmarks/`.

## 7. Required README / GitHub-Facing Changes

- Add logo at the top of README.
- Add benchmark, caveat, visualization, and artifact provenance sections.
- Embed generated benchmark visuals directly in README.
- State clearly that current committed metrics come from very small samples and are not broad performance claims.
- Keep runtime-policy claims honest about BSEO eligibility and fallback.

## 8. File-Level Revision Plan

### Documentation

- `README.md`
- `ARCHITECTURE.md`
- `docs/architecture/README.md`
- `docs/architecture/truthlens-architecture-blueprint.mmd`
- `docs/architecture/REFERENCE_ARCHITECTURE.md` (new)
- `docs/benchmarks/README.md` (new)

### Runtime / Contracts

- `libs/shared-schemas/python/truthlens_shared_schemas/contracts.py`
- `libs/shared-schemas/src/index.ts`
- `libs/model-serving/python/truthlens_model_serving/scorer.py`
- `libs/model-serving/python/truthlens_model_serving/verification.py` (new)
- `libs/policy-engine/python/truthlens_policy_engine/engine.py`
- `libs/explanation-engine/python/truthlens_explanation_engine/explainer.py`
- client adapters in `apps/api`, `apps/extension`, and `apps/android-client` if schema updates require it

### Benchmarking / Visualization

- `scripts/render_benchmark_visualizations.py` (new)
- `scripts/update_readme_benchmark_fragments.py` (new if needed)
- `docs/benchmarks/latest/*` (generated)

### Tests

- schema tests
- policy/provenance tests
- verification-trigger tests
- benchmark generator smoke tests
- architecture render smoke tests

## 9. Verification Plan

- targeted schema and runtime tests during contract work
- benchmark generator smoke tests after visualization scripts land
- full verification at the end:
  - `py -m uv run pytest`
  - `py -m uv run ruff check .`
  - `py -m uv run mypy .`
  - `pnpm test`
  - `pnpm build`
  - `pnpm docs:render-architecture`
  - benchmark generation script(s)

## 10. Audit Verdict

TruthLens already matches the target architecture in broad structure, but not yet in publication discipline and not yet in explicit selective-verification provenance. The correct response is a surgical consolidation:

1. preserve the existing runtime and BSEO strengths
2. make selective verification explicit as a separate contract layer
3. surface benchmark/artifact truth honestly and reproducibly
4. update docs, visuals, and GitHub-facing state to match the runtime and artifacts exactly
