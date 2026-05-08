# TruthLens Architecture Assets

Authoritative architecture order:

1. [Reference architecture](./REFERENCE_ARCHITECTURE.md)
2. [Architecture contract](../../ARCHITECTURE.md)
3. [Architecture diagnosis](./TRUTHLENS_ARCHITECTURE_REVISION_DIAGNOSIS.md)
4. [Architecture overview source](./truthlens-architecture-blueprint.mmd)
5. [Runtime decision flow source](./truthlens-runtime-decision-flow.mmd)
6. [Governance feedback loop source](./truthlens-governance-feedback-loop.mmd)

Rendered asset families:

- [Architecture overview SVG](./truthlens-architecture-blueprint.svg)
- [Architecture overview PNG](./truthlens-architecture-blueprint.png)
- [Runtime decision flow SVG](./truthlens-runtime-decision-flow.svg)
- [Runtime decision flow PNG](./truthlens-runtime-decision-flow.png)
- [Governance feedback loop SVG](./truthlens-governance-feedback-loop.svg)
- [Governance feedback loop PNG](./truthlens-governance-feedback-loop.png)

Interpretation rules:

- solid blocks represent committed implemented architecture
- contract-colored blocks represent runtime-safe boundaries or shared governed surfaces
- dashed blocks represent optional or future extensions
- the overview figure must show the system shape without collapsing perception, verification, policy, and explanation into one opaque block
- the overview figure must show the Chromium extension beta, hosted Render/FastAPI API, ad/non-video guard, local user-side reranking, Adaptive Semantic Evidence Router, BSEO, manual report/verify flow, event capture, governance, and public truth surfaces
- the runtime flow figure must make the scoring-to-verification-to-policy-to-explanation sequence legible on GitHub without zooming
- the runtime flow figure must show that `minimal_creative + clean` reduces mismatch pressure without becoming a safe-pass, and that ineligible ad/external cards no-op before scoring or event capture
- the governance loop figure must show browser observation / feedback intake as a supplemental, split-safe path rather than as a hidden training write
- the governance loop figure must distinguish local/public tester feedback, hosted events, creator/operator adjudication, governed benchmark truth, and runtime promotion truth
- BSEO must appear as an interpretation / policy / search layer, not as the core classifier
- BSEO wording should reflect TruthLens' positive-bias preservation for benign contexts and negative-bias penalty for deceptive packaging

Regenerate all committed architecture renders with:

```powershell
pnpm docs:render-architecture
```

The README should embed the three PNG renders as the GitHub-primary artifacts. The SVG renders remain the editable source outputs and must stay sharp enough for direct repository-page viewing.

If the runtime, artifacts, or README drift away from these visuals, update the visuals rather than leaving two competing versions of TruthLens in the repo.
