# Hosted Beta Verification Status

Date: 2026-04-12

This note records the current proof status for the committed hosted-beta contract.

## Current committed contract

- deployment contract: [Render hosted beta](./render-beta.md)
- provisioning blueprint: [`render.yaml`](../../render.yaml)
- extension beta path: [Extension beta install](../beta-install.md)

## Live verification target checked

- `https://truthlens-beta-api.onrender.com/`
- `https://truthlens-beta-api.onrender.com/health`
- `https://truthlens-beta-api.onrender.com/ready`
- `https://truthlens-beta-api.onrender.com/model-info`
- `https://truthlens-beta-api.onrender.com/policy-info`

## Result

As of this check, the committed hostname is **not a live hosted beta proof**.

Observed behavior:

- all checked endpoints returned `404 Not Found`
- response headers included `x-render-routing: no-server`

## Interpretation

The repo now contains a real hosted-beta contract and a provisionable Render blueprint, but live deployment proof is still open.

That means the following are **not yet proven complete** from the public repo truth alone:

- live `/ready` health on the committed hosted origin
- model bundle presence at the hosted runtime path
- live extension-to-hosted scoring flow against a real API instance
- hosted Postgres-backed feedback and browser-observation persistence
- restart behavior on the hosted stack

## What is proven already

- the hosted-beta topology is documented
- the Render blueprint is committed
- the API code now supports Postgres-backed runtime events
- the extension/runtime contracts are aligned to an external hosted API model

## Next closure gate

Before treating any hosted origin as public beta truth, complete all of the following on a live deployed instance:

1. set the real `TRUTHLENS_PUBLIC_API_BASE`
2. provision the promoted `model_bundle.pkl` into the mounted runtime storage root
3. verify `/health`, `/ready`, `/model-info`, `/policy-info`, `/score-item`, `/batch-score`, `/feedback`, `/browser-observation`, and `/metrics`
4. verify at least one hosted feedback event and one hosted browser observation are persisted through Postgres
5. verify extension flow against the live hosted origin
