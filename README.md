<p align="center">
  <img src="docs/logo/truthlens_logo.png" alt="TruthLens logo" width="220" />
</p>

# TruthLens

TruthLens is a multimodal browser-extension, API, trainer, and Android-share system for detecting, explaining, filtering, and supporting human review of misleading video packaging.

The repository already contains a hybrid scoring stack, optional learned paths, anomaly and history sidecars, BSEO policy/search code, trainer and simulation artifacts, explanation contracts, extension/mobile surfaces, and architecture tooling. This README is the GitHub-facing truth surface for what is actually committed now.

## Repo Status

Current committed root-repo truth:

- baseline runtime is separated into perception -> fusion/calibration -> selective verification -> policy -> explanation
- selective deep verification is explicit and fail-soft
- heavy LLM assistance remains downstream in review and report drafting, not in the baseline hot path
- a compatible `configs/thresholds/bseo-policy.json` is now committed and the root runtime is promoted to `bseo-live`
- current governance artifacts now mark `bseo-live` as both eligible and recommended for the committed runtime guardrails
- committed benchmarks are larger than the earlier tiny-sample snapshot, but they are still repository artifacts rather than production performance claims

## Architecture Summary

TruthLens runtime is organized as:

1. input and context
2. core multimodal perception
3. fusion and calibration
4. selective deep verification
5. policy and action selection
6. explanation and review provenance

BSEO is not the core classifier. It is placed as a bias-structured interpretation, policy, search, and artifact layer downstream of calibrated scoring.

## BSEO

`BSEO` stands for `Bias Structured Evolutionary Optimization`.

In TruthLens, BSEO is the committed answer to a practical moderation problem: the system should not pretend that all bias must be erased. It should instead structure bias so the runtime can separate legitimate expressive context from manipulative clickbait packaging.

This is the central design claim:

- TruthLens does not seek "bias-free" modeling as an absolute.
- TruthLens seeks class-conditioned bias interpretation.
- Bias is treated as either positive context that should be preserved or negative pressure that should be penalized.

That means TruthLens handles two directions of bias at the same time:

- positive bias preservation for `music`, `art`, `satire`, `gaming`, and similar honest formats where dramatic visuals, stylized artwork, joke framing, album covers, or non-literal thumbnails are often legitimate
- negative bias penalty for deceptive packaging where title urgency, thumbnail shock design, transcript mismatch, channel priors, or uncertainty patterns point toward report-worthy clickbait behavior

So BSEO is not the core classifier. The classifier still produces the calibrated base score, class hypothesis, confidence, uncertainty, and mismatch-related signals. BSEO sits downstream as the interpretation, policy, search, and artifact layer that decides how those signals should be weighted for the inferred content class before TruthLens selects an action.

The committed implementation starts from a bias primitive vector:

$$
b(x) = \left[
w_{\mathrm{sens}}(x),
r_{\mathrm{cross}}(x),
d_{\mathrm{prior}}(x),
g_{\mathrm{conf}}(x),
u_{\mathrm{cal}}(x)
\right].
$$

where:

- $w_{\mathrm{sens}}(x)$ corresponds to `sensational_weight`
- $r_{\mathrm{cross}}(x)$ corresponds to `crossmodal_rigidity`
- $d_{\mathrm{prior}}(x)$ corresponds to `channel_prior_dependency`
- $g_{\mathrm{conf}}(x)$ corresponds to `genre_confusion`
- $u_{\mathrm{cal}}(x)$ corresponds to `uncertainty_calibration`

These primitive terms are not abstract rhetoric. They are the actual TruthLens lenses for answering questions such as:

- is the packaging aggressively sensational
- is the system over-enforcing literal thumbnail-to-transcript alignment in a domain where non-literal packaging is normal
- is the model leaning too much on channel prior risk
- is the content class ambiguous in a way that should reduce certainty
- is uncertainty itself a reason to escalate to review instead of auto-suppress

Class-conditioned policy scoring then extends the calibrated base score with structured bias terms:

$$
s_{\mathrm{policy}}(x,\theta) =
\mathrm{clip}\!\left(
s_{\mathrm{base}}(x)
+ 0.14\,m(x)\,\omega_{\mathrm{mis}}(c)
+ 0.10\,q(x)\,\omega_{\mathrm{sens}}(c)
+ 0.08\,d_{\mathrm{prior}}(x)\,\tau_{\mathrm{prior}}
+ 0.06\,u(x)\,\beta_{\mathrm{unc}}
+ \Delta_{\mathrm{class}}(c)
\right).
$$

where $\theta$ is the BSEO control genome, $c$ is the inferred content class, $m(x)$ is mismatch pressure, $q(x)$ is sensational pressure, $d_{\mathrm{prior}}(x)$ is channel-prior dependency, and $u(x)$ is uncertainty-sensitive escalation.

In implementation terms, `\theta` carries the knobs that TruthLens evolves and commits as an artifact:

- global thresholds for `badge`, `blur`, `ask-report`, and `hide`
- class-conditioned threshold offsets
- class-conditioned mismatch weights
- class-conditioned sensational weights
- `channel_prior_temperature`
- `uncertainty_escalation_bias`

That is the core BSEO point: the same surface signal is not interpreted the same way for every class. A loud thumbnail in `music` or `art` should not be treated like a loud thumbnail attached to a fake-official `promo` or sensational `news` claim.

The class-conditioned threshold frame is:

$$
\tau_c(\theta) = \tau_{\mathrm{global}}(\theta) + \delta_c(\theta).
$$

In practice, the runtime clips and normalizes these class-conditioned thresholds before applying them.

The resulting runtime action can be written as:

$$
a(x) = A\!\left(s_{\mathrm{policy}}(x,\theta), \tau_c(\theta)\right),
$$

with

$$
a(x) \in \{\mathrm{none}, \mathrm{badge}, \mathrm{blur}, \mathrm{askreport}, \mathrm{hide}\}.
$$

Here `\mathrm{askreport}` is the mathematical shorthand for the runtime action exposed in configuration and UI as `ask-report`.

TruthLens therefore does not ask only "is this risky." It also asks "risky relative to which content class, which guardrail, and which kind of bias." A stylized album cover can legitimately lower literal-rigidity pressure; a fake trailer or emergency-alert package should push the policy score upward toward review or suppression.

The committed search objective follows the same weighted structure as the implementation in `libs/evaluation/src/truthlens_evaluation/bseo.py`:

$$
J(\theta) =
0.45\,D(\theta)
+ 0.20\,C(\theta)
+ 0.15\,K(\theta)
+ 0.10\,M(\theta)
- 0.05\,L(\theta)
- 0.05\,G(\theta).
$$

with:

- `D(\theta)` = detection quality
- `C(\theta)` = context sensitivity
- `K(\theta)` = calibration quality
- `M(\theta)` = mutation stability
- `L(\theta)` = channel lock-in risk
- `G(\theta)` = genre confusion penalty

BSEO also tracks negative-bias movement explicitly rather than hiding everything inside one scalar:

$$
\Delta B_{\mathrm{neg}} =
B_{\mathrm{neg}}(\theta_{\mathrm{child}})
- B_{\mathrm{neg}}(\theta_{\mathrm{parent}}).
$$

Mutation acceptance is therefore not just "bigger objective wins." In committed TruthLens terms, a candidate is only a meaningful improvement when it improves or preserves detection quality without introducing harmful bias side effects against benign classes. The acceptance intuition can be written as:

$$
\alpha(\theta_{\mathrm{child}})=1
$$

only when

$$
J(\theta_{\mathrm{child}}) > J(\theta_{\mathrm{parent}}),
$$

$$
\Delta B_{\mathrm{neg}} \le \varepsilon_{\mathrm{neg}},
$$

$$
\mathrm{FPR}_{\mathrm{benign}} \le \varepsilon_{\mathrm{fpr}},
$$

and

$$
\mathrm{ECE} \le \varepsilon_{\mathrm{ece}}.
$$

That is why BSEO matters to TruthLens specifically:

- it protects benign expressive formats from being flattened by naive literalism
- it increases scrutiny for deceptive factual or fake-official packaging
- it produces a policy artifact that can be inspected, versioned, benchmarked, and promoted
- it turns bias from a hidden nuisance into an explicit moderation-control surface

In plain terms: TruthLens uses BSEO as the runtime's synthetic-subjective interpretation layer. It is the mechanism that lets the system treat "bias we want less of" and "bias we must preserve as context" as two different problems instead of one collapsed score.

This is the committed TruthLens interpretation frame, not a claim that the repo has solved general bias modeling. The claim is narrower and implementation-bound: TruthLens works better when bias is classified, weighted, and guarded according to context than when it is treated as something that must be removed absolutely.

Authoritative architecture references:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [Reference architecture](docs/architecture/REFERENCE_ARCHITECTURE.md)
- [Architecture diagnosis](docs/architecture/TRUTHLENS_ARCHITECTURE_REVISION_DIAGNOSIS.md)
- [Architecture visual notes](docs/architecture/README.md)

## Architecture Visual

### System Overview

[![TruthLens architecture blueprint](docs/architecture/truthlens-architecture-blueprint.png)](docs/architecture/truthlens-architecture-blueprint.svg)

Open the vector render: [System overview SVG](docs/architecture/truthlens-architecture-blueprint.svg)

### Runtime Decision Flow

[![TruthLens runtime decision flow](docs/architecture/truthlens-runtime-decision-flow.png)](docs/architecture/truthlens-runtime-decision-flow.svg)

Open the vector render: [Runtime decision flow SVG](docs/architecture/truthlens-runtime-decision-flow.svg)

### Governance And Feedback Loop

[![TruthLens governance and feedback loop](docs/architecture/truthlens-governance-feedback-loop.png)](docs/architecture/truthlens-governance-feedback-loop.svg)

Open the vector render: [Governance and feedback loop SVG](docs/architecture/truthlens-governance-feedback-loop.svg)

- [Mermaid source](docs/architecture/truthlens-architecture-blueprint.mmd)
- [SVG render](docs/architecture/truthlens-architecture-blueprint.svg)
- [PNG render](docs/architecture/truthlens-architecture-blueprint.png)
- [Runtime decision flow source](docs/architecture/truthlens-runtime-decision-flow.mmd)
- [Runtime decision flow SVG](docs/architecture/truthlens-runtime-decision-flow.svg)
- [Runtime decision flow PNG](docs/architecture/truthlens-runtime-decision-flow.png)
- [Governance feedback loop source](docs/architecture/truthlens-governance-feedback-loop.mmd)
- [Governance feedback loop SVG](docs/architecture/truthlens-governance-feedback-loop.svg)
- [Governance feedback loop PNG](docs/architecture/truthlens-governance-feedback-loop.png)

## Current Implemented Runtime

Committed baseline paths:

- text path
- vision path
- metadata path
- cross-signal mismatch logic

Committed optional sidecars and bounded learned paths:

- history path
- anomaly path
- sentence-transformer text path
- tiny-CNN and ViT thumbnail paths
- LSTM temporal history path

Committed downstream layers:

- fusion and calibration
- explicit selective deep verification triggers and provenance
- separate policy engine
- explanation engine with path, verification, and policy evidence
- distinct `Report` and `Verify` draft-generation flows with heuristic fail-soft suggestions when Gemini is unavailable
- user-facing manual review tags that stay separate from core `content_class` and separate from packaging issue types
- collection-scope review and reporting previews for resolvable YouTube mixes and playlists
- browser observation records with shared provenance and distilled DOM features
- feedback-linked supplemental label candidates and split-safe adjudication intake
- human review and manual report flows

Not in the baseline hot path:

- Gemini wording assistance for report optimization and richer draft text
- any always-on heavy LLM classifier
- unguarded automatic BSEO-live takeover without governance guardrails

## Policy Modes

Supported runtime modes in code:

- `threshold-default`
- `bseo-shadow`
- `bseo-live`

Compatibility aliases:

- `rl-shadow`
- `rl-live`

Committed root configuration today:

- `configs/thresholds/runtime-policy.json` is set to `bseo-live`
- `configs/thresholds/bseo-policy.json` is committed and contract-compatible with the current runtime
- current governance artifacts now clear `bseo-live` for committed use, so the root runtime is promoted to live rather than held in shadow

## Observation And Feedback Intake

TruthLens now treats browser observation and feedback-to-dataset as one shared intake path rather than two disconnected side systems.

- the extension can persist DOM-based browser observation records without any DevTools dependency
- observation records, feedback events, and supplemental label candidates share provenance-aware contracts
- linked feedback and manual reports can create supplemental adjudication candidates in the labeling UI
- manual review submissions can carry selected review tags and collection-scope provenance without writing directly into baseline train/validation/eval splits
- those supplemental candidates are explicitly split-blocked and do not append directly to `train`, `validation`, or `test`
- adjudicated supplemental rows land in separate intake artifacts and require future deterministic ingestion before any training use

## Review And Collection Workflow

- `recommended_action = blur` remains part of the internal policy contract, but the extension now keeps thumbnails visible and presents `blur` as a warning-state rather than a visual obstruction.
- `Report` and `Verify` now use distinct draft intents. `Report` defaults toward `Clickbait`, while `Verify` defaults toward a positive tag such as `Music`, `Tutorial`, `Gaming`, or `Documentary` when the scored context supports it.
- manual review tags are a user-facing classification layer. They are not the same thing as the six packaging issue types (`thumbnail`, `title`, `description`, `transcript`, `channel`, `other`) and they do not replace the core runtime `content_class`.
- when Gemini is not configured or errors during draft suggestion, TruthLens falls back to explicit local heuristics instead of blocking the normal review flow.
- when the extension can resolve a YouTube mix or playlist from DOM and URL context, it opens a collection preview first, requires confirmation, and then applies batch review provenance across the resolved members.
- direct external YouTube reporting for collection scope is best-effort only. TruthLens reports resolved watch URLs item-by-item and never claims that unresolved collection members were externally reported.
- direct YouTube API reporting is account-dependent. If the authenticated account does not expose a usable misleading-report category through `videoAbuseReportReasons`, TruthLens now routes single-item reports straight to YouTube’s in-page report flow instead of first triggering a known failing API call.

## Benchmarking

Benchmark source of truth:

- [Benchmark README](docs/benchmarks/README.md)
- [Latest summary JSON](docs/benchmarks/latest/benchmark_summary.json)
- [Latest summary Markdown](docs/benchmarks/latest/benchmark_summary.md)
- [Latest verify JSON](docs/benchmarks/latest/verify_summary.json)
- [Latest verify Markdown](docs/benchmarks/latest/verify_summary.md)
- [Runtime governance JSON](artifacts/reports/runtime-governance-latest.json)

Current committed snapshot:

| Field | Value |
| --- | --- |
| `build_id` | `build-20260411064344` |
| `model_version` | `baseline-v1-build-20260411064344` |
| `trained_at` | `2026-04-11T06:43:44.245427+00:00` |
| `eval sample_count` | `76` |
| `configured runtime mode` | `bseo-live` |
| `resolved runtime mode` | `bseo-live` |
| `governance recommended mode` | `bseo-live` |
| `max promotable mode` | `bseo-live` |

Current eval vs validation snapshot from committed artifacts:

| Metric | Eval | Validation |
| --- | ---: | ---: |
| Precision | 1.000 | 1.000 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 1.000 |
| ROC AUC | 1.000 | 1.000 |
| PR AUC | 1.000 | 1.000 |
| Calibration error | 0.146 | 0.146 |

Current generated observation and governance snapshot from the same render-time summary:

| Field | Value |
| --- | --- |
| `browser observations` | `1459` |
| `unique observed items` | `671` |
| `score-linked observation rows` | `1459` |
| `shadow observation count` | `911` |

These moving counts are also surfaced in `docs/benchmarks/latest/benchmark_summary.md` and the regenerated intake/governance visuals, which remain the authoritative generated truth surface.

## Metrics Caveats

These numbers are not production claims.

- committed eval sample count is now `76`, which is materially better than the earlier tiny-sample snapshot but still modest
- eval and validation are both very strong on this committed split; that symmetry should be read as a clean repository benchmark, not as broad real-world proof
- overall calibration error remains `0.146`, so ranking confidence is still less mature than the binary F1 snapshot suggests
- per-head metrics are uneven: text/fusion are strong, while history and anomaly remain much weaker sidecars
- current governance artifacts now clear and recommend `bseo-live`, and the committed runtime has been promoted accordingly
- collection-scope review/report support is implemented in the extension and shared schemas, but committed benchmark volume for collection-batch intake may still be zero until the flow is exercised against real browser observations

## Evaluation And Visualization

### Overview

![Benchmark overview](docs/benchmarks/latest/assets/train_validation_eval_overview.svg)

### Per-Head Metrics

![Per-head metrics](docs/benchmarks/latest/assets/per_head_metrics.svg)

### Threshold Sweep

![Threshold sweep](docs/benchmarks/latest/assets/threshold_sweep.svg)

### Drift Summary

![Drift summary](docs/benchmarks/latest/assets/drift_summary.svg)

### Runtime Policy Truth

![Policy mode comparison](docs/benchmarks/latest/assets/policy_mode_comparison.svg)

### Runtime Governance

![Runtime governance summary](docs/benchmarks/latest/assets/runtime_governance.svg)

### Observation And Feedback Intake

![Observation and feedback intake](docs/benchmarks/latest/assets/observation_feedback_intake.svg)

Additional committed assets:

- [Overall metrics table](docs/benchmarks/latest/assets/overall_metrics_table.md)
- [Calibration error chart](docs/benchmarks/latest/assets/calibration_error.svg)
- [Confusion matrix](docs/benchmarks/latest/assets/confusion_matrix_eval.svg)
- [Benchmark provenance card](docs/benchmarks/latest/assets/benchmark_provenance.svg)
- [BSEO bias profile](docs/benchmarks/latest/assets/bseo_bias_profile.svg)
- [Mutation bias atlas](docs/benchmarks/latest/assets/mutation_bias_atlas.svg)
- [Lineage overview](docs/benchmarks/latest/assets/lineage_overview.svg)
- [Metrics dashboard](docs/benchmarks/latest/interactive/metrics_dashboard.html)
- [Threshold explorer](docs/benchmarks/latest/interactive/threshold_explorer.html)
- [BSEO policy dashboard](docs/benchmarks/latest/interactive/bseo_policy_dashboard.html)
- [Mutation atlas explorer](docs/benchmarks/latest/interactive/mutation_atlas.html)
- [Runtime governance dashboard](docs/benchmarks/latest/interactive/runtime_governance_dashboard.html)
- [Observation and feedback intake summary](docs/benchmarks/latest/assets/observation_feedback_intake.svg)

## Artifact Provenance

Current benchmark inputs:

- `artifacts/trained_models/latest/model_info.json`
- `artifacts/eval_runs/build-20260411064344.json`
- `artifacts/eval_runs/build-20260411064344-simulation.json`
- `artifacts/eval_runs/build-20260411064344-bseo-report.json`
- `artifacts/eval_runs/build-20260411064344-bseo-lineage.json`
- `artifacts/eval_runs/build-20260411064344-mutation-bias-atlas.json`
- `artifacts/drift_reports/build-20260411064344.json`
- `configs/thresholds/default.json`
- `configs/thresholds/bseo-policy.json`
- `configs/thresholds/runtime-policy.json`
- `artifacts/reports/runtime-governance-latest.json`
- `artifacts/reports/browser_observations.jsonl` when browser observation intake has been exercised
- `datasets/labels/supplemental_candidates/latest.json` when supplemental candidates have been derived
- `datasets/labels/supplemental_adjudication/*.json` and `datasets/labels/supplemental_gold/*.jsonl` for split-blocked supplemental adjudication

## Quick Start

### Python

```powershell
py -m uv sync --group dev
py -m uv run python scripts/run_api.py --reload
py -m uv run pytest -q
py -m uv run ruff check .
py -m uv run mypy .
```

### TypeScript

```powershell
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

### Docs And Benchmark Assets

```powershell
pnpm runtime:promote-auto
pnpm docs:render-architecture
pnpm docs:render-benchmarks
pnpm docs:render-verify
```

### Training / Simulation Reproduction

```powershell
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.pipeline
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.train
py -m uv run python scripts/run_truthlens_module.py truthlens_trainer.simulate
```

## Repository Structure

- `apps/` runnable surfaces: API, extension, Android client, trainer, labeling UI
- `libs/` shared schemas, feature extraction, model serving, policy, explanation, evaluation, governance, data pipeline
- `configs/` thresholds and runtime/training configuration
- `artifacts/` trained models, eval runs, drift reports, exported runtime artifacts
- `docs/` architecture, benchmarks, and supporting documentation
- `tests/` unit, integration, and end-to-end verification

## V1 / V2 / V3 Alignment

`V1`

- explicit-feature bounded-path core
- text + vision + metadata + fusion + calibration
- extension + API + explanation baseline
- no mandatory deep verifier in hot path
- no runtime RL dependency

`V2`

- anomaly sidecar
- stronger history path
- transcript/title mismatch
- selective deep verification
- richer benchmark and visualization pipeline
- stronger human review flows

`V3`

- runtime-safe BSEO shadow/live policy
- mutation-bias atlas consumption when artifacts exist
- guarded policy optimization from evolution or bandit artifacts
- broader operator analytics

## Honest Limitations

- committed benchmarks are materially broader than before, but README still should not read like a product benchmark sheet
- calibration and per-head stability still lag behind the clean fused F1 snapshot
- history and anomaly paths remain useful sidecars, not equally mature peers to text and fusion
- `bseo-live` is now the committed runtime mode because current governance artifacts clear the live guardrails
- observation and supplemental intake artifacts depend on actual runtime use, so a clean repo snapshot may legitimately show zero supplemental volume
- current repo truth is stronger on architecture separation and governance discipline than on real-world benchmark maturity

## Next Stages

1. keep growing benchmark coverage beyond the current `76` eval rows so README metrics become less brittle
2. keep exercising live BSEO runtime with richer browser-observation history and supplemental adjudication volume
3. keep turning benchmark and provenance artifacts into richer operator dashboards and runtime governance views
