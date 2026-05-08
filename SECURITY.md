# Security Policy

## Supported Scope

TruthLens is currently an active beta/research codebase. Security reports should focus on:

- credential handling or secret exposure
- hosted API abuse paths
- unsafe report automation or OAuth flows
- data leakage across review, feedback, or observation paths
- dependency or configuration issues that materially weaken the hosted beta posture

## Reporting A Vulnerability

Do not open public GitHub issues for suspected vulnerabilities.

Instead, use GitHub Security Advisories (private disclosure) if available and include:

- a short summary
- affected path, surface, or workflow
- reproduction steps or proof of concept
- impact assessment
- any suggested mitigation

If Security Advisories are not available, open a minimal public issue without sensitive details and request a private contact channel from maintainers before sharing reproduction steps.

Do not include access tokens, API keys, OAuth secrets, or personal data in any report.

## What To Include

The most useful reports include:

- a short summary
- affected path, surface, or workflow
- reproduction steps or proof of concept
- impact assessment
- any suggested mitigation

## Current Beta Boundaries

For the first hosted beta:

- direct YouTube OAuth/report-submit is not part of the public external beta contract
- Gemini is server-side optional and outside the baseline hot path
- runtime event persistence is expected to be Postgres-backed in hosted beta, with local fallback reserved for development

Reports that concern these boundaries are especially useful.
