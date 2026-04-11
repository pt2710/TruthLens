# Render Hosted Beta

TruthLens' first hosted beta target is a single-instance stateful deployment on Render.

A starter Render Blueprint is committed at [`render.yaml`](../../render.yaml) so the hosted beta contract is executable instead of doc-only.
The committed repo does not currently publish a verified live Render hostname as default truth. The current proof status is tracked in [Hosted beta verification](./hosted-beta-verification.md).

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
- `TRUTHLENS_YOUTUBE_DIRECT_REPORTING_ENABLED=false`

Optional:

- `TRUTHLENS_API_KEY`
- `TRUTHLENS_GEMINI_API_KEY`
- `TRUTHLENS_GEMINI_MODEL`

## Runtime artifact contract

Public source control keeps:

- policy JSONs
- `artifacts/trained_models/latest/model_info.json`
- `artifacts/reports/runtime-governance-latest.json`
- dataset cards and curated manifests

Hosted beta must supply the promoted model bundle outside the public source tree. The current runtime expects the promoted bundle at:

- `/var/data/truthlens/artifacts/trained_models/latest/model_bundle.pkl`

and may also persist runtime-local files under:

- `/var/data/truthlens/artifacts/reports/`

## Beta notes

- extension is the first supported external beta surface
- Android is config-parity only and not part of the first external launch
- direct YouTube OAuth/report-submit stays disabled in the first hosted beta
- Gemini remains optional and outside the baseline hot path
- `TRUTHLENS_PUBLIC_API_BASE` should be finalized to the actual Render hostname after the service is created
