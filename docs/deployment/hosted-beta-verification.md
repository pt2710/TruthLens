# Hosted Beta Verification Status

Date: 2026-04-18

This note records the current proof status for the committed hosted-beta contract.
It supersedes the earlier "not yet live" snapshot and the later write-path regression snapshot.
The Render service is live at:

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
- live `POST /score-item`, `POST /batch-score`, `POST /browser-observation`, `POST /feedback`, and `GET /feedback-summary` return `200` again after the trained-runtime redeploy
- `event_store` resolves to `postgres` on the live service
- the promoted model bundle and aligned model metadata are present at the mounted runtime storage path used by the live host
- the live runtime surfaces a trained artifact on `/ready` and `/model-info`
- extension-origin traffic to the live host has been manually verified in DevTools with successful `batch-score`, `browser-observation`, and `feedback` requests
- restart survivability after hosted writes has been proven with a pre-restart write run, a manual Render restart, a post-restart read check, and a second post-restart write run

## Current live runtime truth

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

Latest hosted verification proof:

- pre-restart write run (`artifacts/reports/restart-pre.json`) finished with:
  - `metrics_after.score_events_total = 436`
  - `metrics_after.feedback_events_total = 9`
  - `metrics_after.browser_observations_total = 178`
- post-restart read-only check (`artifacts/reports/restart-post-readonly.json`) finished with:
  - `score_events_total = 436`
  - `feedback_events_total = 9`
  - `browser_observations_total = 178`
- post-restart write run (`artifacts/reports/restart-post-write.json`) finished with:
  - `metrics_after.score_events_total = 439`
  - `metrics_after.feedback_events_total = 10`
  - `metrics_after.browser_observations_total = 179`
  - `postgres_persistence_proven = true`

Interpretation:

- the live service is real and reachable
- the policy artifact is present and active
- the promoted model bundle is present and actively loaded as a trained runtime artifact
- hosted Postgres-backed runtime event persistence is proven on the API surface
- the same persisted counters survived a manual Render restart without dropping
- the service continued accepting new writes after the restart, which closes the restart-survivability gate

## Manual proof note

`scripts/verify_hosted_beta.py` is intentionally an API-surface verifier.
It can prove hosted GETs, hosted writes, and Postgres-backed persistence, but it does not auto-close the extension gate because extension proof requires manual DevTools evidence from the browser plugin itself.

That manual extension proof is now satisfied by successful live extension-origin requests for:

- `POST /batch-score`
- `POST /browser-observation`
- `POST /feedback`

all targeting `https://truthlens-beta-api.onrender.com` from the loaded extension.

## Remaining open closure gates

No hosted-beta proof gates remain open for the current Wave 1 closure target.

Operational follow-up that does not reopen closure:

1. monitor Render memory headroom, because the Render event log also recorded a separate `used over 512MB` instance failure before recovery on 2026-04-18
2. if that memory pressure repeats, either reduce runtime memory usage further or move the service off the current Starter memory limit

## Recommended verification commands

Run the hosted verification helper against the live host:

```powershell
py -m uv run python scripts/verify_hosted_beta.py --write-events --report-path artifacts/reports/hosted-beta-live-proof.json
```

For restart-survivability, the proof sequence is:

```powershell
py -m uv run python scripts/verify_hosted_beta.py --write-events --report-path artifacts/reports/restart-pre.json
py -m uv run python scripts/verify_hosted_beta.py --report-path artifacts/reports/restart-post-readonly.json
py -m uv run python scripts/verify_hosted_beta.py --write-events --report-path artifacts/reports/restart-post-write.json
```

These generated reports are local proof artifacts and should not be committed.

## Current status summary

This repo should no longer describe the hosted beta as "not yet live proof" or as currently blocked on the hosted write path.

The correct statement is now:

- **live service confirmed**
- **GET endpoint proof green**
- **hosted write-path proof green**
- **promoted model bundle present and loaded as a trained artifact**
- **extension-to-live-host proof closed**
- **restart-survivability after hosted writes closed**
