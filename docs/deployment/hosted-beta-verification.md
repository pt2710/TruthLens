# Hosted Beta Verification Status

Date: 2026-04-13

This note records the current proof status for the committed hosted-beta contract.
It supersedes the earlier "not yet live" snapshot. The Render service is now live at:

- `https://truthlens-beta-api.onrender.com`

## Current committed contract

- deployment contract: [Render hosted beta](./render-beta.md)
- provisioning blueprint: [`render.yaml`](../../render.yaml)
- extension beta path: [Extension beta install](../beta-install.md)
- hosted verification helper: [`scripts/verify_hosted_beta.py`](../../scripts/verify_hosted_beta.py)

## Live proof now closed

The following hosted-beta closure steps are now confirmed:

- the real hosted origin exists and serves traffic at `https://truthlens-beta-api.onrender.com`
- `TRUTHLENS_PUBLIC_API_BASE` is set to that live hosted origin in Render
- live `/ready` health is green
- live `GET /health`, `GET /ready`, `GET /model-info`, `GET /policy-info`, and `GET /metrics` all return `200`
- `event_store` resolves to `postgres` on the live service
- an earlier hosted proof run produced non-zero `truthlens_feedback_events_total` and `truthlens_browser_observations_total`, which proves the live API has successfully read persisted runtime events back through the Postgres-backed store at least once

## Current live runtime truth

The live service is up, but hosted-beta closure is still incomplete.

Current observed runtime truth on the live host:

- `/health` reports `env=beta`
- `/health` reports `event_store=postgres`
- `/ready` reports `ready=true`
- `/ready` reports `artifact_status=compatible`
- `/model-info` reports `mode=trained`
- `/model-info` reports `model_version=baseline-v1-build-20260412135829`
- `/policy-info` reports `policy_mode=bseo-live`
- `/policy-info` reports `resolved_policy_mode=bseo-live`
- `/metrics` reports `truthlens_policy_bseo_artifact_available 1`

Interpretation:

- the live service is real and reachable
- the policy artifact is present and active
- hosted Postgres-backed runtime event persistence is now minimally proven
- the promoted model bundle and aligned model metadata are now present at the mounted runtime storage path used by the live host
- the live runtime now surfaces a trained artifact on `/ready` and `/model-info`
- the current deployed image now returns `502` across the hosted write path (`/score-item`, `/batch-score`, `/browser-observation`, `/feedback`, and `/feedback-summary`) even though GET endpoints remain green
- the committed beta runtime now includes a runtime-safe fallback fix so hosted beta can keep the promoted artifact truth while avoiding unstable learned-head execution in the scoring hot path
- the earlier minimal Postgres write proof is therefore historical evidence, not current closure proof; the write-path closure gate is open again until a rerun succeeds under the trained runtime

## Remaining open closure gates

The following hosted-beta proof items are still open:

1. redeploy the Render service with the committed runtime-safe beta scoring fix so the hosted write path (`/score-item`, `/batch-score`, `/browser-observation`, `/feedback`, `/feedback-summary`) stops returning `502`
2. rerun hosted verification and confirm the write checks return `200` while retaining the trained artifact truth (`artifact_status=compatible`, non-bootstrap `model_version`)
3. re-prove Postgres-backed feedback and browser-observation persistence under the trained runtime after the current write-path regression is fixed
4. verify extension flow against the live hosted origin, including at least one live `batch-score`, one live `browser-observation`, and one live `feedback` request originating from the extension itself
5. prove restart behavior after hosted writes, since Wave 1 closure now treats restart survivability as an explicit gate

## Recommended verification command

Run the hosted verification helper against the live host:

```powershell
py -m uv run python scripts/verify_hosted_beta.py --write-events --report-path artifacts/reports/hosted-beta-live-proof.json
```

This script:

- verifies the live GET endpoints
- performs a minimal hosted proof run for `score-item`, `batch-score`, `browser-observation`, and `feedback`
- records whether hosted Postgres-backed runtime persistence is proven from the API surface

## Current status summary

This repo should no longer describe the hosted beta as "not yet live proof."

The correct statement is now:

- **live service confirmed**
- **GET endpoint proof remains green**
- **promoted model bundle present and loaded as a trained artifact**
- **hosted write-path proof is currently regressed to `502` and must be re-closed before extension and restart proof can finish**
