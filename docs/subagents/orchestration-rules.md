# TruthLens Subagent Orchestration Rules

This document operationalizes Workpack 21.

## Core Rules

- The main agent owns integration, final verification, commit discipline, and push behavior.
- Subagents are bounded contributors; they do not redefine architecture or workflow contracts.
- Parallel live edits on the same file are forbidden without explicit worktree discipline.

## File Ownership

- Every delegated task must name writable paths and read-only paths before execution.
- When output is exploratory or likely to conflict, the subagent should return a patch proposal instead of direct integration.
- Shared contract files such as `AGENTS.md`, `CODEX_WORKFLOW.md`, `ARCHITECTURE.md`, and cross-language schemas require orchestrator approval before merge.

## Merge Discipline

- Integrate one workpack result at a time.
- Run the relevant `TEST` and `VERIFY` steps after each integration batch.
- Do not accumulate multiple unverified parallel patches into one commit.

## Summary Format

Each delegated result must include:

- scope
- changed files
- tests run
- results
- risks
- recommended next step

## Failure Handling

- Failed subagent work is not force-merged.
- If a delegated patch does not pass local verification, the orchestrator either repairs it centrally or discards it.
- Remote push failures do not justify losing verified local commits.
