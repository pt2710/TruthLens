# TruthLens Reference Architecture

This document defines the current reference architecture for the committed TruthLens repository.

It is intentionally stricter than a roadmap note. If runtime, contracts, diagrams, or README disagree with this file, this file wins and the repo should be revised.

## 1. Runtime Topology

TruthLens runtime is organized as:

1. input and context
2. core multimodal perception
3. fusion and calibration
4. selective deep verification
5. policy and action selection
6. explanation and review provenance

This is not a single linear neural chain. Optional learned components plug into bounded paths and preserve explicit fallbacks.

## 2. Input And Context Layer

Required runtime inputs:

- `title`
- `thumbnail`
- `description_snapshot`
- `transcript_excerpt` when available
- browser-observation distilled DOM features when the extension captures them
- watch-page and metadata signals
- channel history and channel-level priors
- user preferences, prior corrections, muted channels
- runtime surface context and provenance

Input normalization must preserve enough context for both baseline scoring and later review flows.

## 3. Core Multimodal Perception Layer

Required baseline paths:

- text path
- vision path
- metadata path
- mismatch logic across title, thumbnail, transcript, and metadata

Optional but committed sidecars:

- history path
- anomaly path
- bounded learned encoders for text, vision, and temporal history

Rules:

- optional learned paths must degrade safely to explicit feature paths
- missing bytes, missing artifacts, or incompatible dependencies must not break baseline scoring
- BSEO is not part of this layer
- Gemini is not part of this layer

## 4. Fusion And Calibration Layer

The perception layer feeds a fused score and then a calibrated score.

This layer must surface:

- `fused_score`
- `calibrated_score`
- `confidence`
- `uncertainty`
- path-level contributors

The calibrated score is the final output of the classifier itself. Policy is downstream from here.

## 5. Selective Deep Verification Layer

Selective deep verification is explicit, not implicit.

Allowed triggers:

- high risk
- high uncertainty
- high mismatch
- threshold-near cases
- report or review flows

Allowed verification behaviors:

- transcript/title contradiction checks
- deeper semantic consistency checks
- claim plausibility checks
- review-oriented rationale synthesis
- downstream human-review LLM assistance

Rules:

- no heavy always-on LLM in baseline hot path
- verification must fail soft
- verification must emit provenance fields, not hidden score mutations
- verification may inform policy, but it does not replace calibrated perception

## 6. Policy And Action Layer

Policy consumes:

- calibrated score and uncertainty
- selective verification provenance
- thresholds
- feedback bias
- channel bias
- user personalization
- BSEO artifacts when present and eligible

Supported runtime modes:

- `threshold-default`
- `bseo-shadow`
- `bseo-live`

Compatibility aliases:

- `rl-shadow` -> `bseo-shadow`
- `rl-live` -> `bseo-live`

Rules:

- action selection happens here, not inside the scorer
- BSEO can influence policy only through runtime-safe guardrails
- missing, stale, or incompatible BSEO artifacts must fall back cleanly
- the committed root repo must not claim live BSEO control unless the artifact is actually present and eligible

## 7. BSEO Placement

BSEO is treated as:

1. a bias-structured interpretation frame
2. a bias-aware policy and search layer
3. a runtime-guarded downstream decision influence
4. an artifact-producing offline evaluation subsystem
5. an explanation-enriching context layer

BSEO is not the core classifier.

BSEO artifacts may include:

- class-conditioned thresholds
- control genomes
- mutation lineage logs
- mutation-bias atlases
- shadow/live divergence summaries
- guardrail eligibility signals

## 8. Explanation And Review Provenance Layer

User-facing and developer-facing explanations must be traceable to:

- path signals
- fused signal
- verification state
- policy decision
- runtime mode

The shared contract should surface:

- path scores
- path contributors
- verification status, triggers, reasons, and summary
- action decision basis
- policy mode and resolved policy mode
- artifact provenance

Explanation must not pretend a policy or verification reason came from the classifier if it did not.

## 9. Observation, Feedback, And Supplemental Intake

Observation and feedback intake is an explicit adjunct to the runtime, not an implicit training write.

Rules:

- browser observation capture must work from DOM-derived context and may not require DevTools
- observation records, feedback events, and label candidates must share provenance-aware contracts
- supplemental candidates may flow into adjudication and labeling UI review
- adjudicated supplemental rows must remain separate from direct `train` / `validation` / `test` artifacts
- any future ingestion of supplemental rows must re-enter deterministic dataset governance and split assignment

## 10. Offline Artifact Pipeline

The offline system produces:

- trained model artifacts
- evaluation reports
- simulation reports
- drift reports
- threshold profiles
- optional BSEO policy artifacts
- benchmark summaries and visuals

README benchmark claims must be derived from committed artifacts only.

## 11. Fallback Rules

Mandatory fallback behavior:

- if optional encoders fail, use baseline explicit paths
- if transcript is absent, do not fake transcript-based certainty
- if verification cannot run, return `failed-soft` or `not-requested`
- if BSEO artifact is missing or incompatible, stay on threshold policy
- if explanation evidence is sparse, do not invent causality

## 12. V1 / V2 / V3 Alignment

`V1`

- explicit-feature bounded-path core
- text + vision + metadata + fusion + calibration
- extension + API + baseline explanation
- no mandatory deep verification in hot path
- no runtime RL dependency

`V2`

- anomaly sidecar
- stronger history path
- transcript/title mismatch
- explicit selective deep verification
- richer benchmark and visualization pipeline
- stronger human review flows

`V3`

- runtime-safe BSEO shadow/live policy
- mutation-bias atlas consumption when artifacts exist
- contextual bandits or evolution as guarded policy optimization
- richer operator analytics

Truth in the current root repo:

- the codebase supports more than the root runtime configuration currently promotes
- GitHub-facing docs must distinguish implemented support from committed active runtime state
