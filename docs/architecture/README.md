# TruthLens Architecture Assets

Authoritative architecture order:

1. [Reference architecture](./REFERENCE_ARCHITECTURE.md)
2. [Architecture contract](../../ARCHITECTURE.md)
3. [Architecture diagnosis](./TRUTHLENS_ARCHITECTURE_REVISION_DIAGNOSIS.md)
4. [Blueprint source](./truthlens-architecture-blueprint.mmd)
5. [Blueprint SVG](./truthlens-architecture-blueprint.svg)
6. [Blueprint PNG](./truthlens-architecture-blueprint.png)

Interpretation rules:

- solid blocks represent committed implemented architecture
- dashed blocks represent optional, offline-only, or future extensions
- the blueprint must show the separation between perception, verification, policy, and explanation
- BSEO must appear as an interpretation / policy / search layer, not as the core classifier

Regenerate the committed blueprint renders with:

```powershell
pnpm docs:render-architecture
```

If the runtime, artifacts, or README drift away from these visuals, update the visuals rather than leaving two competing versions of TruthLens in the repo.
