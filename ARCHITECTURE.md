# TruthLens Architecture

## Mission

TruthLens is a multimodal system for detecting, explaining, filtering, and supporting semi-automated review of misleading video content through a browser extension, a model/policy backend, and a companion Android share client.

## System Layers

1. Extension layer
2. Mobile client layer
3. Cross-platform client contract layer
4. Data discovery layer
5. Acquisition layer
6. Normalization layer
7. Dataset governance layer
8. Feature layer
9. Inference layer
10. Policy layer
11. Explanation layer
12. Feedback layer
13. Evaluation layer
14. Orchestration layer

## Repository Structure

The repository is organized as a monorepo with:

- `apps/` for runnable surfaces such as the API, extension, trainer, and labeling UI
- `libs/` for shared schemas, data pipeline code, governance, policy, explanation, model serving, and evaluation
- `infra/` for Docker, Compose, CI, DB, and migrations
- `configs/` for environment, threshold, model, labeling, and dataset configuration
- `datasets/` for tracked manifests/cards and untracked runtime data areas
- `artifacts/` for model and evaluation outputs
- `docs/` for architecture, API, workpacks, decisions, and subagent documentation
- `tests/` for unit, integration, e2e, and fixture coverage

## Core Contracts

- All scoring outputs must include `risk_score`, `confidence`, `uncertainty`, `recommended_action`, and `reasons`.
- Active recommendations require at least one explanation string.
- Auto-actions may not trigger from raw model score alone.
- Channel history is a supporting signal, not a sole verdict.
- Feedback events must be auditable and versioned.
- Model training is blocked until dataset governance artifacts are complete.
- Optional learned encoder paths must degrade safely to explicit fallback paths when dependencies, artifacts, or runtime media bytes are unavailable.
- Runtime BSEO policy may only override threshold policy when compatible artifacts exist and guardrails pass.
- Mobile and extension review flows must share stable versioned schemas rather than diverging client-specific payloads.

## BSEO Interpretation Frame

TruthLens treats BSEO as a bias-and-interpretation layer rather than a hardcoded rule engine.

Two prior lists drive that layer:

- benign-by-default contexts that should not be auto-classified as clickbait merely because they are dramatic, stylized, or commercial
- suspicious-by-default patterns that should trigger higher skepticism because they rely on misleading promises, fake urgency, fake authority, or systematic packaging mismatch

This frame is evaluated across the same operational parameters used elsewhere in the system:

- `Thumbnail`
- `Title`
- `Description`
- `Transcription`
- `Channel`
- `Other`

The current runtime taxonomy remains fixed to `news`, `commentary`, `documentary`, `music`, `art`, `satire`, `gaming`, `promo`, and `unknown`, but broader priors such as tutorials, reviews, sports, education, official trailers, and user verification are folded into those classes as positive or negative bias frames.

## V1 / V2 / V3 Boundaries

- V1: data pipelines, first dataset build, baseline explicit-feature models, calibration, FastAPI scoring, extension overlay, blur/hide, feedback capture, simple explanations
- V2: optional sentence-transformer text path, optional tiny-CNN thumbnail path, optional LSTM history path, VAE anomaly signal, transcript-title mismatch, personalization, replay simulator
- V3: optional ViT thumbnail encoder, runtime BSEO action policy (`threshold-default`, `bseo-shadow`, `bseo-live`), mobile analyze/review contract, Android companion/share client, BSEO search / replay / mutation-atlas artifacts promoted into runtime-safe policy artifacts

Post-V3 roadmap remains separate from shipped scope:

- richer video understanding beyond thumbnail/title/metadata/transcript excerpts
- stronger end-to-end multimodal encoders beyond the current bounded optional paths
- deeper moderation analytics and operator tooling
- broader cross-platform expansion beyond the current Android companion scope

## Subagent-Friendly Boundaries

Safe parallelization targets:

- docs/bootstrap
- repo hygiene and CI
- data discovery / collection / normalization / auditing
- shared schemas
- extension scaffolding
- API scaffolding
- model research
- evaluation and simulation
