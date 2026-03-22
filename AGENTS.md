# TruthLens Agents Guide

Project identity: `TruthLens`

Purpose:
Build a multimodal browser-plugin and backend system for detection, filtering, explanation, and semi-automated reporting support for misleading video content.

Execution principle:
`PROBE -> HYGIENE -> TEST -> PATCH -> VERIFY -> REPORT`

Core rules:
- See `CODEX_WORKFLOW.md` for execution protocol and workpack discipline.
- See `ARCHITECTURE.md` for system structure, layering, contracts, and implementation boundaries.
- These two documents are authoritative for workflow and architecture.
- Do not create an alternative root structure.
- Keep commits small, explainable, and verified.
- New workpacks must respect existing contracts.
- Use subagents only for bounded, low-coupled tasks.
- Parallel agents must not write to the same files without explicit orchestration.
- Do not run parallel live edits on the same files without explicit worktree discipline.
- Data collection and dataset governance are part of the implementation scope.
- No model training may proceed on unversioned or unaudited datasets.
