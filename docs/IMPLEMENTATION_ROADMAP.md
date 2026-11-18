# Implementation roadmap

This roadmap begins only after the source audit. It is ordered to avoid building the wrong product or duplicating existing YJ64 components.

## Phase 1 — Research and architecture (current)

- [x] Verify the new repository and its default branch.
- [x] Identify the exact candidate repositories for Multi-AI Chat Desktop, Yes-Brainer and Synode.
- [x] Inspect project READMEs, selected source/docs and licenses.
- [x] Inspect YJ64 Engineering Core Gateway and the YJ-64 application cloud API/worker read-only.
- [x] Record comparison, architecture proposal and integration boundary.
- [ ] Owner review of the architecture and commercial licensing strategy.

## Phase 2 — Contract and skeleton

- [ ] Decide project license and third-party notice policy.
- [ ] Freeze internal resource identities and event envelope.
- [ ] Define provider adapter interfaces for API and browser-session types.
- [ ] Define the internal Council run state machine and result schema.
- [ ] Define the compatibility mapping for `yj64.council-api.v1`.
- [ ] Create the monorepo skeleton, CI, lint/type checks, tests and container health checks.

## Phase 3 — API-first MVP

- [ ] Implement user/workspace/session persistence and isolation.
- [ ] Implement two API provider adapters and streaming individual chats.
- [ ] Implement one Council workspace with independent parallel responses.
- [ ] Add a common chat/event stream and manual message forwarding.
- [ ] Add deterministic tests for multiple conversations using the same provider.
- [ ] Add cancellation, idempotency, retry classification and recovery.

## Phase 4 — Council deliberation

- [ ] Implement independent conclusions.
- [ ] Implement critique/rebuttal rounds with bounded context.
- [ ] Implement explicit consensus evaluation with dissent preservation.
- [ ] Implement optional voting and aggregate result.
- [ ] Implement arbitration and final synthesis.
- [ ] Test disagreement, missing evidence, provider failure, timeout and round-cap outcomes.

## Phase 5 — Research and evidence

- [ ] Add pluggable search and page-fetch providers.
- [ ] Store source URL, retrieval time, content hash, excerpts and evidence IDs.
- [ ] Add shared and per-participant research modes.
- [ ] Add source comparison and contradiction detection.
- [ ] Ensure model-generated statements are not mislabeled as retrieved facts.

## Phase 6 — Browser Agent

- [ ] Add isolated Playwright worker containers.
- [ ] Implement explicit user login/onboarding and protected browser profile storage.
- [ ] Start with one supported provider adapter and one browser profile per account.
- [ ] Verify target chat, send acknowledgement and completed response.
- [ ] Add adapter health, screenshots/traces with redaction, retries and stop controls.
- [ ] Add CAPTCHA/MFA/security-challenge stop states; no bypass.

## Phase 7 — Parallel execution and product readiness

- [ ] Support multiple independent Council runs and browser tasks.
- [ ] Add tenant-scoped budgets, quotas, audit events and retention controls.
- [ ] Add secure secret management, backups, restore tests and observability.
- [ ] Run concurrency, isolation, failure-recovery and security tests.
- [ ] Verify mobile PWA behavior and desktop/tablet layouts.

## Phase 8 — YJ64 integration and deployment

- [ ] Implement and test the `yj64.council-api.v1` compatibility adapter.
- [ ] Validate requests/results against the shared JSON Schema.
- [ ] Run a staging integration against an explicitly configured Engineering Core Gateway.
- [ ] Confirm that native YJ-64 Council and Browser Council remain independently selectable.
- [ ] Deploy API and workers using portable containers; do not place long-running model/browser work in a short-lived edge function.
- [ ] Publish verified end-to-end evidence, actual limitations and rollback procedure.

## Initial implementation block after owner approval

1. Select the project license and dependency-notice approach.
2. Confirm React/TypeScript PWA + FastAPI + PostgreSQL + Docker worker stack.
3. Define provider and Council event contracts with JSON Schema.
4. Add CI and the smallest runnable API/web skeleton.
5. Implement the first two API adapters and isolated parallel chats before browser automation.

## Acceptance rule

A phase is complete only when its acceptance criteria pass and evidence is recorded. A successful build is not proof of working provider sessions, Council consensus semantics, browser automation, multi-user isolation or YJ64 end-to-end integration.
