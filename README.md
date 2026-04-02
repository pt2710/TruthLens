# TruthLens

TruthLens is a multimodal browser plugin and backend system for detecting, explaining, filtering, and supporting semi-automated reporting of misleading video packaging. The current implementation combines thumbnail, title, metadata, transcript-derived, anomaly, and channel-history signals with a policy layer that decides whether content should stay untouched, receive a badge, blur, trigger a review prompt, or be hidden locally.

## Why TruthLens Exists

Video platforms are full of packaging decisions that users have to interpret quickly: thumbnails, titles, metadata snippets, channel history, and the occasional transcript cue. Misleading or clickbait framing rarely lives in one field alone. It usually emerges from the way several cues are combined.

TruthLens exists to make that packaging legible. The project is designed around two beliefs:

- Multimodal reasoning is necessary because misleading framing is often a mismatch between visual, textual, and historical context.
- Human-in-the-loop review is necessary because score-driven automation alone is too blunt for moderation-like decisions.

## How TruthLens Works

At runtime, the extension observes YouTube feed cards and watch-page context, extracts available title, thumbnail, metadata, transcript, channel, and user-preference signals, and sends them through the local scoring stack. The model layer produces calibrated risk, confidence, and uncertainty estimates. A policy layer then applies thresholds, feedback bias, channel bias, contextual-bandit offsets, and user personalization to decide the recommended action.

That runtime loop is only one part of the system. The repository also contains the offline data-build, training, evaluation, and simulation stack that produces model artifacts, threshold profiles, drift reports, and replay-search outputs. Human feedback closes the loop through report/verify flows, score event logging, feedback event logging, channel profile aggregation, and later threshold adaptation.

## Architecture Blueprint

![TruthLens architecture blueprint](docs/architecture/truthlens-architecture-blueprint.svg)

The blueprint above is the visual companion to the authoritative architecture contract in [ARCHITECTURE.md](ARCHITECTURE.md). Solid blocks and arrows represent implemented architecture. Dashed blocks and arrows represent planned or future extensions. The current visual now distinguishes baseline explicit feature paths from the implemented optional learned paths that can be activated by environment and config.

For AI/ML readers, the diagram now distinguishes the currently shipped layer taxonomy from planned neural extensions. That distinction is deliberate: the current scorer is a hybrid stack with explicit engineered features, optional bounded neural encoders, logistic fusion/calibration, and clear fallback behavior, while stronger end-to-end neural components remain roadmap items rather than live runtime claims.

- [Mermaid source](docs/architecture/truthlens-architecture-blueprint.mmd)
- [SVG render](docs/architecture/truthlens-architecture-blueprint.svg)
- [PNG render](docs/architecture/truthlens-architecture-blueprint.png)
- [Architecture visual notes](docs/architecture/README.md)

## Current Implemented Model

TruthLens currently ships a seven-head multimodal scoring stack:

- `text`: `title-encoder`
- `vision`: `thumbnail-feature-head`
- `metadata`: `tabular-risk-head`
- `history`: `temporal-channel-head`
- `anomaly`: `packaging-vae-anomaly-head`
- `fusion`: `multimodal-fusion-head`
- `calibration`: `probability-calibration-head`

The important detail is that the runtime has both baseline explicit feature paths and optional learned encoder paths.

Implemented today:

- text baseline path: sparse `CountVectorizer` bigrams feeding a scikit-learn logistic text head
- text learned option: `sentence-transformer` embeddings feeding the same logistic text-head contract
- vision baseline path: `vision-v2` engineered thumbnail features feeding a logistic vision head
- vision learned option: `tiny-cnn-thumbnail` feeding the vision score directly when real thumbnail bytes are available at runtime
- metadata path: handcrafted tabular feature assembly feeding a logistic metadata head
- history baseline path: sequence-summary channel features feeding a logistic history head
- history learned option: `lstm-sequence` temporal encoder trained over recent per-channel sequences
- anomaly path: VAE anomaly scoring over combined thumbnail and metadata packaging features
- fusion layer: logistic fusion over stacked head probabilities
- calibration layer: Platt-style logistic calibration over fused probabilities

The current implementation is therefore no longer “purely logistic everywhere,” but it is still deliberately auditable. The learned components are narrow, bounded, and optional. They plug into the same explicit output contract instead of replacing the whole system with an opaque end-to-end model.

The scoring stack still does **not** claim:

- a ViT-based thumbnail encoder
- a full end-to-end multimodal transformer
- an LLM inside the scoring classifier
- autonomous hidden reporting from raw score alone

Gemini remains outside the scoring classifier. It is used in the human-review path for manual report drafting and wording optimization, not for the core `risk_score` path.

The runtime output contract includes:

- `risk_score`
- `confidence`
- `uncertainty`
- `recommended_action`
- `reasons`
- `explanation_id`
- `explanation_summary`
- `evidence`

The current default threshold profile in `configs/thresholds/default.json` is:

- `badge_threshold`: `0.20`
- `blur_threshold`: `0.45`
- `report_prompt_threshold`: `0.65`
- `hide_threshold`: `0.80`

Those base thresholds are then adjusted by feedback bias, contextual-bandit offsets, channel-specific bias, strict-mode behavior, muted channels, and prior correction history before the extension applies actions locally.

## Training and Policy Adaptation

TruthLens is built around a gated pipeline rather than ad hoc model training.

The data side currently follows this path:

1. discovery
2. acquisition
3. normalization
4. deduplication
5. split manifest generation
6. dataset card and audit output generation

Model training is blocked until those governance artifacts exist and validate.

The training and evaluation stack then:

- fits the baseline text, vision, metadata, and history heads
- optionally resolves and trains learned encoder paths for text, vision, and temporal history when the environment supports them
- trains the VAE anomaly head over lower-risk packaging examples
- trains the fusion head on validation-time probability stacks
- trains the calibration head over fusion output
- exports model artifacts and model metadata
- writes evaluation outputs, calibration summaries, confusion metrics, and per-head reports

TruthLens also includes a simulation and search layer that is already represented in code and artifacts:

- threshold sweep
- Q-table construction
- policy derivation
- Bellman state values
- replay simulation
- evolutionary threshold search
- contextual bandit threshold adjustments
- drift reporting

This policy layer matters because TruthLens is explicitly not meant to trigger moderation-like decisions from raw score alone. Runtime actions are policy-gated and context-aware.

Planned next-step model families remain clearly separate from the shipped runtime stack:

- stronger text encoders beyond the current optional sentence-transformer path
- stronger CNN / ViT vision encoders beyond the current tiny CNN
- richer temporal encoders beyond the current optional LSTM sequence path
- deeper transcript / video understanding

## Human Review and Reporting

TruthLens supports semi-automated review, not hidden autonomous moderation.

Today that means:

- manual report suggestions with Gemini plus local heuristic fallback
- transparent/non-clickbait verification flows
- explainable report prompts and verify prompts in the extension
- YouTube reporting support where the platform and account state allow it
- structured local feedback capture for both negative and positive signals

The boundary is intentional:

- raw model output does not silently submit reports on its own
- policy can prompt the user to review
- the user remains part of the final reporting or verification action

## Repository Structure

TruthLens is a monorepo organized around clear subsystem boundaries:

- `apps/`
  - runnable surfaces such as the API, extension, trainer, and labeling UI
- `libs/`
  - shared schemas, feature extraction, model serving, explanation, policy, evaluation, governance, and data pipeline logic
- `configs/`
  - threshold profiles, model metadata space, and other runtime/training configuration
- `datasets/`
  - tracked manifests plus the governance-oriented structure around dataset builds
- `artifacts/`
  - trained model bundles, evaluation runs, drift reports, score/feedback logs, and runtime reports
- `docs/`
  - architecture notes, API docs, workpacks, and subagent guidance
- `infra/`
  - infrastructure, CI, database, and deployment support
- `tests/`
  - unit, integration, and end-to-end coverage

Core repository guidance lives in:

- [AGENTS.md](AGENTS.md)
- [CODEX_WORKFLOW.md](CODEX_WORKFLOW.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

## Quick Start

### Python

```powershell
py -m uv sync --group dev
py -m uv run pytest
py -m uv run ruff check .
py -m uv run mypy .
py -m uv run python scripts/run_api.py --reload
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.pipeline
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.train
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.simulate
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.smoke
```

### TypeScript

```powershell
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
pnpm build
pnpm docs:render-architecture
```

### Smoke Validation

```powershell
make smoke
```

This runs dataset build, model training, simulation, and API endpoint validation in an isolated smoke root and writes a summary report under `artifacts/reports/`.

## Roadmap

### Phase 1: Current Baseline

- multimodal browser extension with local overlay behavior
- FastAPI scoring backend
- explicit score/result contracts
- explanation generation and feedback capture
- governance-first data/build/training workflow
- threshold tuning, replay simulation, and drift reporting

### Phase 2: Stronger Context and Personalization

- optional sentence-transformer text path
- optional tiny-CNN thumbnail path
- VAE anomaly scoring
- optional temporal LSTM history path
- richer multimodal context modeling across thumbnail, description, transcript, and watch-page signals
- more robust channel-pattern reasoning
- stronger local personalization and verification/report prompting
- better handling of domain-specific content types such as music, synthetic spam, and recurring template channels

### Phase 3: Cross-Platform and Deeper Moderation Analytics

- cross-platform TruthLens clients
- Android support
- richer moderation analytics and reporting surfaces
- stronger multimodal encoders and deeper video understanding beyond the current optional neural paths
- more advanced learning loops layered on top of the current explicit policy system
