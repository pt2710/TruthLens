# TruthLens Codex Workflow

## Execution Cycle

Every workpack follows:

```text
PROBE -> HYGIENE -> TEST -> PATCH -> VERIFY -> REPORT
```

## Scoped Changes

- Keep workpacks minimal and bounded.
- Avoid mixing training, serving, data collection, and UI logic in the same module.
- Preserve root integrity: `TruthLens/` is the only valid top-level project root.
- Prefer additive scaffolding over speculative implementation for later phases.

## Test Requirements

- Add or update tests before large changes.
- Add at least one regression or contract test for each new public contract.
- Maintain smoke tests for bootstrap workpacks.
- Run Python static checks and tests before commit.
- Run TypeScript build, tests, and lint/type checks before commit.

## Commit and Push Discipline

- Commit only after `VERIFY` passes for the workpack.
- Use small, meaningful commits with `type(scope): short summary`.
- Push verified milestones to the configured GitHub remote when possible.
- If push fails, keep local commits and report the failure.

## Subagent Delegation Rules

- Use subagents only for bounded, parallelizable work with clear file ownership.
- Do not allow multiple live edits of the same file in parallel.
- Require subagents to report: scope, changed files, tests run, results, risks, and recommended next step.
- Use worktrees when parallel branches would otherwise collide.

## Failure Handling

- Stop and report when a contract cannot be honored safely.
- Document broken assumptions and environment drift in the report output.
- Do not silently downgrade contracts or remove required verification steps.

## Data Build Gates

Model training may not start until the following exist and validate:

- source manifest
- raw acquisition outputs
- interim normalized records
- deduplication report
- split manifest
- dataset build manifest
- dataset card
- audit report
