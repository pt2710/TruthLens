# TruthLens Architecture Visuals

`ARCHITECTURE.md` remains the authoritative architecture contract for TruthLens.

This directory contains the visual companion assets that explain the implemented system as a blueprint-style block diagram:

- [TruthLens architecture blueprint source](./truthlens-architecture-blueprint.mmd)
- [TruthLens architecture blueprint SVG](./truthlens-architecture-blueprint.svg)
- [TruthLens architecture blueprint PNG](./truthlens-architecture-blueprint.png)

To regenerate the committed renders from the Mermaid source:

```powershell
pnpm docs:render-architecture
```

Interpretation rule:

- Solid blocks and solid arrows represent implemented architecture.
- Dashed blocks and dashed arrows represent planned or future extensions.

Current implemented optional neural paths that should now appear in the blueprint:

- sentence-transformer text embeddings
- tiny CNN thumbnail encoder
- ViT thumbnail encoder
- VAE packaging-anomaly head
- temporal LSTM history encoder
- BSEO interpretation frames and class-conditioned guardrails
- feature-flagged runtime BSEO action policy with RL compatibility export
- cross-platform mobile review contract
- Android Jetpack Compose companion/share client

The blueprint should continue to keep those separate from still-planned extensions such as richer end-to-end multimodal stacks, deeper transcript/video understanding, and broader cross-platform expansion beyond the current Android companion scope.
