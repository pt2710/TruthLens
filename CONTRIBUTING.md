# Contributing

TruthLens is a public hosted/open beta. It is not production-grade, and current reporting is human-assisted/manual submission, not autonomous mass reporting.

License: Apache-2.0 (see `LICENSE`).

## Where To Start

- Issues: reproducible bugs, false positives, false negatives, and concrete documentation fixes.
- Discussions: Q&A, ideas, ethics/governance, roadmap, and broader beta feedback. See `docs/community/discussions.md`.
- Pull requests: code and doc changes that match repo contracts and include verification.

GitHub Wiki is intentionally disabled. Canonical docs live in `README.md`, `docs/`, and GitHub Pages.

## Quick Start: Hosted Beta Extension Test

External beta testers do not need local Gemini, YouTube, Render, Postgres, or API secrets for this path.

```powershell
git clone https://github.com/pt2710/TruthLens.git
cd TruthLens
pnpm install
pnpm --filter @truthlens/extension build
```

Then open Chromium or Chrome:

```text
chrome://extensions
Developer mode: ON
Load unpacked
Select: apps/extension/dist
```

## Developer Setup

```powershell
pnpm install
py -m uv sync
```

Common checks:

```powershell
py -m uv run python scripts/release_hygiene_audit.py
py -m uv run pytest tests
py -m uv run ruff check .
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

## DCO / Sign-Off

This repo requires sign-off for web-based commits, and contributors should also sign off local commits.

Use:

```powershell
git commit -s -m "message"
```

Sign-off is a Developer Certificate of Origin style provenance statement. It confirms you have the right to submit the contribution; it is not a copyright assignment.

## Working Style

- Follow `PROBE -> DIAGNOSE -> CONTRACT -> TEST -> PATCH -> VERIFY -> REPORT` (see `CODEX_WORKFLOW.md`).
- Keep changes small and contract-driven.
- Respect layer boundaries between extension, API, data, governance, training, and evaluation code.
- Avoid committing generated artifacts unless repo policy explicitly allows them.

## Sensitive Areas (Extra Care Required)

- scoring
- BSEO/policy
- semantic routing
- benchmark/model artifacts and governance
- privacy/dataflow
- report/verify flows
- YouTube/Gemini/Render integrations

## Secrets And Safety

Never commit API keys, OAuth tokens, `.env` files, Render secrets, Gemini keys, YouTube secrets, or GitHub tokens. Redact sensitive information in issues, screenshots, and logs.
