# Privacy And Dataflow

TruthLens is a hosted/open beta. It is not production-grade privacy infrastructure, and testers should avoid submitting private, sensitive, or confidential material through beta review flows.

## What The Extension Sends

When a scoreable YouTube video/feed item is processed, the extension may send the hosted API a scoring request containing:

- item id or URL-derived item reference
- title snapshot
- channel name and channel URL when available
- thumbnail reference URL, not raw thumbnail media bytes from the browser
- description or metadata snippets visible in the page when available
- lightweight runtime context such as surface, route context, local channel-history features, and user-context flags

The extension sends this when it scores feed/watch-page content, when the user explicitly opens report or verify flows, and when feedback or browser-observation intake is enabled for the beta.

## Local Browser State

The extension can keep local session/cache state for:

- score responses for the current browsing session
- local user preferences such as muted channels and reranking settings
- queued feedback events when the hosted API is temporarily unavailable
- channel trust/profile context derived from the local beta workflow

Local reranking is browser-side only. It does not alter YouTube's backend recommender.

## Hosted State

The hosted beta can persist:

- score audit events
- browser observation records
- feedback events
- manual report / verify outcomes
- route and policy context used to explain runtime decisions

Hosted write paths are intended for beta diagnostics, review workflow continuity, and model/policy evaluation governance. They are not a guarantee of permanent retention or production privacy controls.

## Feedback And Benchmark Truth

Ordinary public/test-user feedback is not automatically promoted into global benchmark truth. It remains supplemental runtime evidence unless it passes a controlled creator/operator ingestion, adjudication, split-governance, and manifest path.

Creator/operator feedback, when used, must be traceable through governed manifests and kept separate from ordinary local-user feedback.

## Reporting Boundary

TruthLens-assisted reporting is human-assisted/manual in the public beta. Report and verify sheets open only on explicit user action, and TruthLens does not perform autonomous mass reporting.
