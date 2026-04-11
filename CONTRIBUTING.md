# Contributing

TruthLens is still in a controlled beta/research phase. The project is open to contributions, but the safest first lanes are docs, install/onboarding polish, tests, UI friction reduction, and other low-risk fixes.

`main` is the canonical trunk for contributor work. `master` is deprecated and not part of the public contributor flow for the hosted-beta phase.

## Working Style

- Follow `PROBE -> DIAGNOSE -> CONTRACT -> TEST -> PATCH -> VERIFY -> REPORT`.
- Keep changes small and contract-driven.
- Do not introduce alternative root structures or placeholder project names.
- Respect layer boundaries between extension, API, data, governance, training, and evaluation code.

## Before Commit

- Run Python checks: `pytest`, `ruff check`, `mypy`
- Run TypeScript checks: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`
- Run release hygiene checks when touching repo surface or public-release files: `python scripts/release_hygiene_audit.py`
- Verify git status is intentional and reviewable
- Base new branches and pull requests on `main`

## First Contribution Lanes

- `docs`
- `good first issue`
- `extension`
- `api`
- `training`
- `policy`
- `dataset-governance`

## Commit Format

Use:

```text
type(scope): short summary
```

Examples:

- `chore(repo): bootstrap truthlens monorepo skeleton`
- `docs(agents): add workflow and architecture references`
- `feat(api): add initial scoring stub`

## Subagents

- Use only for bounded work with explicit file ownership.
- Do not run concurrent edits on the same files without worktree discipline.
