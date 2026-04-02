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
