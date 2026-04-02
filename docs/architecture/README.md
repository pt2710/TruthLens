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
- VAE packaging-anomaly head
- temporal LSTM history encoder

The blueprint should continue to keep those separate from still-planned extensions such as ViT-scale vision encoders, stronger end-to-end multimodal stacks, and cross-platform clients.
