# Render Hosted Beta

TruthLens' first hosted beta target is a single-instance stateful deployment on Render.

A starter Render Blueprint is committed at [`render.yaml`](../../render.yaml) so the hosted beta contract is executable instead of doc-only.
The currently verified live hosted beta origin is:

- `https://truthlens-beta-api.onrender.com`

The current proof status is tracked in [Hosted beta verification](./hosted-beta-verification.md).

## Reference topology

- one Render web service from `infra/docker/api.Dockerfile`
- one Render Postgres database for runtime events
- one persistent disk mounted at `/var/data/truthlens`
- no Redis requirement in the beta-critical path

The committed Blueprint currently provisions:

- a `truthlens-beta-api` Docker web service
- a `truthlens-beta-db` Postgres database
- a persistent disk mounted at `/var/data/truthlens`

## Required environment

Set these on the Render web service:

- `TRUTHLENS_ENV=beta`
- `TRUTHLENS_PUBLIC_API_BASE=https://<your-render-host>`
- `TRUTHLENS_DATABASE_URL=<Render Postgres connection string>`
- `TRUTHLENS_RUNTIME_EVENT_STORE=postgres`
- `TRUTHLENS_LOCAL_EVENT_FALLBACK_ENABLED=false`
- `TRUTHLENS_STORAGE_ROOT=/var/data/truthlens`
- `TRUTHLENS_YOUTUBE_DIRECT_REPORTING_ENABLED=true`

Optional:

- `TRUTHLENS_API_KEY`
- `TRUTHLENS_GEMINI_API_KEY`
- `TRUTHLENS_GEMINI_MODEL`
- `TRUTHLENS_GEMINI_API_BASE`
- `TRUTHLENS_YOUTUBE_CLIENT_ID`
- `TRUTHLENS_YOUTUBE_CLIENT_SECRET`
- `TRUTHLENS_YOUTUBE_REDIRECT_URI`

## Render environment notes

- `TRUTHLENS_GEMINI_API_KEY` is designed to be set as a normal Render secret environment variable. A free-tier Gemini key is sufficient for the current beta because Gemini is only used as occasional wording assistance and heuristic fallback repair, not as a required hot-path classifier.
- The starter Blueprint now exposes direct YouTube OAuth/report-submit as part of the hosted-beta contract, but that path is still deployment- and account-gated:
  - the deployment must have `TRUTHLENS_YOUTUBE_DIRECT_REPORTING_ENABLED=true`
  - the deployment must also provide `TRUTHLENS_YOUTUBE_CLIENT_ID`, `TRUTHLENS_YOUTUBE_CLIENT_SECRET`, and either `TRUTHLENS_PUBLIC_API_BASE` or `TRUTHLENS_YOUTUBE_REDIRECT_URI`
  - the connected YouTube account must expose a usable misleading-report category through `videoAbuseReportReasons`
- If any of those conditions fail, TruthLens keeps the user on the watch/feed page and falls back to YouTube's in-page report flow plus linked local TruthLens feedback.

## Runtime artifact contract

Public source control keeps:

- policy JSONs
- `artifacts/trained_models/latest/model_info.json`
- `artifacts/reports/runtime-governance-latest.json`
- dataset cards and curated manifests

Hosted beta must supply the promoted model bundle outside the public source tree. The current runtime expects the promoted bundle at:

- `/var/data/truthlens/artifacts/trained_models/latest/model_bundle.pkl`

and the aligned model metadata at:

- `/var/data/truthlens/artifacts/trained_models/latest/model_info.json`

and may also persist runtime-local files under:

- `/var/data/truthlens/artifacts/reports/`

To provision the promoted runtime model into the active storage root, use:

```powershell
py -m uv run python scripts/provision_runtime_model.py --bundle C:\path\to\model_bundle.pkl
```

When `TRUTHLENS_STORAGE_ROOT=/var/data/truthlens`, this copies:

- the external `model_bundle.pkl` into `/var/data/truthlens/artifacts/trained_models/latest/model_bundle.pkl`
- the aligned `artifacts/trained_models/latest/model_info.json` into `/var/data/truthlens/artifacts/trained_models/latest/model_info.json`

## Beta notes

- extension is the first supported external beta surface
- Android is config-parity only and not part of the first external launch
- direct YouTube OAuth/report-submit is now part of the hosted-beta contract when the deployment is configured for it and the connected account supports it
- Gemini remains optional and outside the baseline hot path
- `TRUTHLENS_PUBLIC_API_BASE` should be finalized to the actual Render hostname after the service is created
