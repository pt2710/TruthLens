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

Instead, contact the maintainer privately at `security@truthlens.dev` and include:

- a short summary
- affected path, surface, or workflow
- reproduction steps or proof of concept
- impact assessment
- any suggested mitigation

You will receive an acknowledgement as quickly as practical. Please allow reasonable time for investigation and remediation before public disclosure.

## Current Beta Boundaries

For the first hosted beta:

- direct YouTube OAuth/report-submit is not part of the public external beta contract
- Gemini is server-side optional and outside the baseline hot path
- runtime event persistence is expected to be Postgres-backed in hosted beta, with local fallback reserved for development

Reports that concern these boundaries are especially useful.
