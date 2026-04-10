# TruthLens Architecture

`docs/architecture/REFERENCE_ARCHITECTURE.md` is the authoritative reference architecture for TruthLens.

This file is the shorter operator-facing contract that points to the runtime truth, repository boundaries, and verification discipline.

## Mission

TruthLens is a multimodal detection, explanation, filtering, and human-review support system for misleading video packaging across browser, API, trainer, and Android surfaces.

## Runtime Order

TruthLens runtime is organized as:

1. input and context
2. core multimodal perception
3. fusion and calibration
4. selective deep verification
5. policy and action selection
6. explanation and review provenance

That order is strict. Perception, verification, policy, and explanation must not be collapsed into one opaque layer.

## Core Contracts

- Scoring outputs must include `risk_score`, `confidence`, `uncertainty`, `recommended_action`, and `reasons`.
- Runtime outputs must also surface provenance for path signals, verification state, policy basis, and artifact lineage.
- Browser observation records and feedback-linked label candidates must use shared provenance-aware contracts.
- Manual review tags must remain separate from the six packaging issue types and separate from the core runtime `content_class`.
- Auto-actions may not trigger from raw model score alone.
- Selective deep verification must be explicit and fail soft.
- Heavy LLM assistance must remain outside the baseline scoring hot path.
- Channel history is a supporting signal, not a sole verdict.
- BSEO may influence policy only through artifact-guarded runtime-safe rules.
- Missing or incompatible artifacts must fall back safely.
- Training is blocked until governance artifacts validate.
- Mobile and extension review flows must share stable schemas rather than drift apart.
- Supplemental browser/feedback intake must stay separate from direct train, validation, and test writes until future deterministic ingestion.
- `recommended_action = blur` may remain in the policy contract for compatibility, but extension presentation must keep thumbnails visible unless a separate `hide` policy is selected.
- `report` and `verify-transparent` must stay behaviorally distinct in draft suggestions, tag defaults, and collection-scope review semantics even though they share the same base contracts.
- direct `/youtube/report` availability is account-dependent; extension flows must preflight capability truth and use YouTube’s in-page flow instead of knowingly triggering an unsupported direct API path.

## Layer Boundaries

### Core Multimodal Perception

Required:

- text path
- vision path
- metadata path
- cross-signal mismatch logic

Optional committed sidecars:

- history path
- anomaly path
- bounded learned encoders

### Selective Deep Verification

Verification may run only when triggered by:

- high risk
- high uncertainty
- high mismatch
- threshold-near cases
- explicit review flows

### Policy And Action

Supported modes:

- `threshold-default`
- `bseo-shadow`
- `bseo-live`

Compatibility aliases:

- `rl-shadow`
- `rl-live`

### Explanation And Review

Explanation must distinguish:

- path reasons
- fused reasons
- verification reasons
- policy reasons
- manual review tag suggestions
- collection-scope provenance

## BSEO Placement

BSEO is:

- a bias-structured interpretation frame
- a bias-aware policy and search layer
- a runtime-guarded downstream influence
- an offline artifact-producing evaluation subsystem
- an explanation-enriching context layer

BSEO is not the core classifier.

## Repository Boundaries

- `apps/` contains runnable surfaces such as API, extension, trainer, Android client, and labeling UI
- `libs/` contains shared schemas, feature extraction, model serving, explanation, policy, evaluation, governance, and data pipeline logic
- `configs/` contains thresholds and runtime/training configuration
- `artifacts/` contains trained models, evaluation runs, drift reports, and runtime-relevant exports
- `docs/` contains architecture, benchmarks, and operational documentation
- `tests/` contains unit, integration, and end-to-end verification

## Observation And Supplemental Intake

- browser observation capture is DOM-based and must not depend on DevTools
- feedback events may link back to observation ids and runtime artifact provenance
- observation and feedback signals can produce supplemental label candidates for adjudication
- collection-scope review actions for mixes and playlists must preserve both collection-level and per-item provenance
- external platform reporting may run best-effort per resolved member, but unresolved collection members must remain explicit skips rather than implied successes
- if the authenticated YouTube account does not expose a usable misleading-report category, direct API reporting is unavailable and the browser extension must route single-item reports through the page flow or store collection review only inside TruthLens
- adjudicated supplemental rows remain split-blocked and excluded from direct train/validation/test use
- future ingestion must assign deterministic split lineage before any supplemental row can become training data

## Architecture Truth Sources

Use these in order:

1. `docs/architecture/REFERENCE_ARCHITECTURE.md`
2. `docs/architecture/truthlens-architecture-blueprint.svg`
3. `docs/benchmarks/latest/benchmark_summary.json`
4. runtime config and artifacts under `configs/` and `artifacts/`

If README or diagrams diverge from committed artifacts or runtime contracts, they are stale and must be revised.
