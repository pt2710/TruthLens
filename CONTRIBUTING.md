# Contributing

## Working Style

- Follow `PROBE -> HYGIENE -> TEST -> PATCH -> VERIFY -> REPORT`.
- Keep changes small and contract-driven.
- Do not introduce alternative root structures or placeholder project names.
- Respect layer boundaries between extension, API, data, governance, training, and evaluation code.

## Before Commit

- Run Python checks: `pytest`, `ruff check`, `mypy`
- Run TypeScript checks: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`
- Verify git status is intentional and reviewable

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
