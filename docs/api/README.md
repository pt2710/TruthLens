# API Docs

TruthLens keeps the public API surface intentionally narrow for the first hosted beta. Runtime configuration may change, but the core endpoints remain stable.

Core endpoints:

- `POST /score-item`
- `POST /batch-score`
- `POST /feedback`
- `POST /browser-observation`
- `GET /health`
- `GET /ready`
- `GET /model-info`
- `GET /policy-info`
- `GET /feedback-summary`
- `GET /metrics`

Manual review and report assistance:

- `POST /manual-report/suggest`
- `POST /manual-report/optimize`

Hosted-beta boundary notes:

- extension is the first supported public beta client
- runtime events are intended to be Postgres-backed in hosted beta
- direct YouTube OAuth/report-submit is not part of the first external beta contract even though the internal endpoints exist behind configuration
