# TruthLens Reference Architecture

This document defines the current reference architecture for the committed TruthLens repository.

It is intentionally stricter than a roadmap note. If runtime, contracts, diagrams, or README disagree with this file, this file wins and the repo should be revised.

## 1. Runtime Topology

TruthLens runtime is organized as:

1. input and context
2. adaptive semantic evidence routing
3. core multimodal perception
4. fusion and calibration
5. selective deep verification
6. policy and action selection
7. explanation and review provenance

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

Extension-specific scoreability rules:

- YouTube watch and shorts video items are scoreable when normal video context is present
- sponsored, promoted, external landing-page, shopping, display-ad, and non-video cards are not scoreable
- ineligible cards must not receive TruthLens badges, action chips, reranking, observation events, feedback targets, or context-menu report/verify targets
- if a card is later identified as non-scoreable, extension-owned UI must be removed from that card

## 3. Adaptive Semantic Evidence Routing

Adaptive semantic evidence routing sits before policy/BSEO and near the scorer's evidence selection.

Rules:

- Route light. Learn deep.
- runtime route is not the same thing as learning capture
- `minimal_creative` lowers literal thumbnail/title/description mismatch pressure for clean music, art, and visualizer-like content
- creative classification is not immunity; scam, fake-official, negative channel-history, prior report, and feedback signals can still escalate scrutiny
- `learning_capture_plan = full_multimodal_capture` preserves route context and existing observation/feedback signals without raw media dumping or direct train/validation/test ingestion
- BSEO remains downstream policy and bias interpretation; the route only conditions evidence pressure and guardrails

## 4. Core Multimodal Perception Layer

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

## 5. Fusion And Calibration Layer

The perception layer feeds a fused score and then a calibrated score.

This layer must surface:

- `fused_score`
- `calibrated_score`
- `confidence`
- `uncertainty`
- path-level contributors

The calibrated score is the final output of the classifier itself. Policy is downstream from here.

## 6. Selective Deep Verification Layer

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

## 7. Policy And Action Layer

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

## 8. BSEO Placement

BSEO is treated as:

1. a bias-structured interpretation frame
2. a bias-aware policy and search layer
3. a positive-bias preservation mechanism for benign or honest contexts such as music, art, satire, and similar non-clickbait classes
4. a negative-bias penalty mechanism for deceptive, report-worthy clickbait packaging
5. a runtime-guarded downstream decision influence
6. an artifact-producing offline evaluation subsystem
7. an explanation-enriching context layer

BSEO is not the core classifier.

BSEO artifacts may include:

- class-conditioned thresholds
- control genomes
- mutation lineage logs
- mutation-bias atlases
- shadow/live divergence summaries
- guardrail eligibility signals

## 9. Explanation And Review Provenance Layer

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
- manual review tag suggestions and selections
- collection scope, resolved member counts, and collection trigger provenance

Explanation must not pretend a policy or verification reason came from the classifier if it did not.

Review-flow rules:

- `report` and `verify-transparent` share contracts but must not share the same intent or default classification behavior
- `report` should default toward `Clickbait`
- `verify-transparent` should default toward an honest-content tag when supported by scored context
- `recommended_action = blur` remains a policy signal, but the extension UI keeps thumbnails visible and uses non-blurring warning presentation
- optional Gemini assistance may improve wording, but draft suggestion must fail soft to local heuristics
- direct `/youtube/report` calls must be gated by account capability truth; if the authenticated account lacks a usable misleading-report category, TruthLens must route single-item reports to the in-page flow instead of knowingly issuing a failing direct API request

## 10. Observation, Feedback, And Supplemental Intake

Observation and feedback intake is an explicit adjunct to the runtime, not an implicit training write.

Rules:

- browser observation capture must work from DOM-derived context and may not require DevTools
- observation records, feedback events, and label candidates must share provenance-aware contracts
- supplemental candidates may flow into adjudication and labeling UI review
- collection-scoped review/report actions must carry explicit `single` / `mix` / `playlist` scope and resolved member counts
- collection batching must preview before apply and must never imply that unresolved external report targets were submitted
- if direct YouTube API reporting is unsupported for the authenticated account, collection reporting must degrade to internal TruthLens provenance only rather than claiming an external batch report
- adjudicated supplemental rows must remain separate from direct `train` / `validation` / `test` artifacts
- any future ingestion of supplemental rows must re-enter deterministic dataset governance and split assignment

## 11. Offline Artifact Pipeline

The offline system produces:

- trained model artifacts
- evaluation reports
- simulation reports
- drift reports
- threshold profiles
- optional BSEO policy artifacts
- benchmark summaries and visuals

README benchmark claims must be derived from committed artifacts only.

## 12. Fallback Rules

Mandatory fallback behavior:

- if optional encoders fail, use baseline explicit paths
- if transcript is absent, do not fake transcript-based certainty
- if verification cannot run, return `failed-soft` or `not-requested`
- if BSEO artifact is missing or incompatible, stay on threshold policy
- if explanation evidence is sparse, do not invent causality

## 13. V1 / V2 / V3 Alignment

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
