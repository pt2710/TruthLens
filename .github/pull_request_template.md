## Summary

- what changed
- why this change is needed
- what surface/contract it affects

## Scope

- in scope:
- out of scope:

## Files Changed

-

## Verification

- [ ] `py -m uv run pytest tests`
- [ ] `py -m uv run ruff check .`
- [ ] `py -m uv run mypy .`
- [ ] `pnpm typecheck`
- [ ] `pnpm lint`
- [ ] `pnpm test`
- [ ] `pnpm build`

## Screenshots / Video (UI Changes)

-

## Affected Areas (check all that apply)

- [ ] extension UI/runtime
- [ ] hosted API
- [ ] scoring/BSEO/policy
- [ ] semantic router
- [ ] benchmark/model artifacts
- [ ] docs/privacy/community

## Safety / Hygiene

- [ ] No secrets/tokens were added (no API keys, OAuth tokens, `.env`, Render/Gemini/YouTube credentials).
- [ ] Public docs do not include local paths (`C:\Users\...`, `file://...`) or private URLs.
- [ ] Benchmark/model claims (if any) are artifact-backed; no overclaims were added.
- [ ] Generated artifacts were not committed unless repo policy explicitly allows them.
- [ ] Hosted beta/manual-report truth was preserved (no autonomous mass-reporting claims).
