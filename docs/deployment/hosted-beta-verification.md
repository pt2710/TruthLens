# Hosted Beta Verification Status

Date: 2026-04-12

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
- live `POST /score-item`, `POST /batch-score`, `POST /browser-observation`, and `POST /feedback` return `200` during hosted proof execution
- `event_store` resolves to `postgres` on the live service
- the hosted proof run produced non-zero `truthlens_feedback_events_total` and `truthlens_browser_observations_total`, which proves the live API is reading persisted runtime events back through the Postgres-backed store

## Current live runtime truth

The live service is up, but hosted-beta closure is still incomplete.

Current observed runtime truth on the live host:

- `/health` reports `env=beta`
- `/health` reports `event_store=postgres`
- `/ready` reports `ready=true`
- `/ready` also reports `artifact_status=missing`
- `/model-info` reports `mode=bootstrap`
- `/model-info` reports `model_version=bootstrap-v0`
- `/policy-info` reports `policy_mode=bseo-live`
- `/policy-info` reports `resolved_policy_mode=bseo-live`
- `/metrics` reports `truthlens_policy_bseo_artifact_available 1`

Interpretation:

- the live service is real and reachable
- the policy artifact is present and active
- hosted Postgres-backed runtime event persistence is now minimally proven
- the promoted model bundle and aligned model metadata are now present at the mounted runtime storage path used by the live host
- live `/ready` now reports `artifact_status=compatible`
- live `/model-info` now reports `model_version=baseline-v1-build-20260412135829`
- live proof writes now report `score_model_version=baseline-v1-build-20260412135829`
- the live service is **still** surfacing `mode=bootstrap`, which means the promoted bundle is present and contract-compatible but the current runtime image is not yet loading it as a trained bundle
- the current Render image installs only baseline dependencies via `uv sync --no-dev`; the promoted bundle requires the committed ML runtime extras present in `pyproject.toml`

## Remaining open closure gates

The following hosted-beta proof items are still open:

1. provision the promoted `model_bundle.pkl` and aligned `model_info.json` into the mounted runtime storage root used by the live service, for example with [`scripts/provision_runtime_model.py`](../../scripts/provision_runtime_model.py)
2. redeploy the Render service with the updated runtime image so the API container installs the committed ML runtime extras and can load the promoted bundle as a trained model
3. rerun hosted verification and confirm `/model-info` moves from `mode=bootstrap` to a trained runtime while retaining `artifact_status=compatible`
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
- **endpoint and Postgres event-path proof substantially advanced**
- **promoted model bundle present and contract-compatible, but runtime image redeploy is still required to exit bootstrap mode**
- **closure still open on trained runtime activation, extension-to-live-host proof, and restart survivability**
