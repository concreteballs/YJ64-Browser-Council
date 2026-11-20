# YJ64 Browser Council — implementation plan

**Repository:** `concreteballs/YJ64-Browser-Council`  
**Working branch:** `research/initial-technical-audit`  
**Purpose:** build Browser Council as an independent, cloud-first product, using verified existing YJ64 capabilities without duplicating them or changing neighboring repositories.  
**Execution model:** each run completes a small batch of related steps (normally 2–4), runs focused checks, records evidence and updates this plan before the next batch.  
**Status:** Batch A is complete. Batch B schema and compatibility baseline are committed; GitHub Actions validated the Draft 2020-12 schema and all 8 contract tests successfully. Full external OpenAPI conformance remains a Phase H gate. Initial API foundation is now in progress.

---

## 0. Project boundaries and execution rules

1. All implementation changes in this plan are limited to this repository and the explicitly selected working branch unless the owner authorizes another target.
2. Do not modify `yj64-clean-bial2modFun5`, `YJ64-Engineering-Core`, or any other repository from this workstream.
3. Browser Council remains an independent product. It must not replace the native YJ-64 Council or Engineering Core.
4. Reuse existing YJ64 services only through documented, versioned contracts. Do not copy their code or create a second model router, durable queue, or Engineering Core Gateway without a demonstrated need and explicit approval.
5. Existing YJ64 capabilities are reference/integration candidates, not proof that a live deployment is ready. Recheck live readiness before integration.
6. Keep API provider connections and authorized browser sessions as distinct connection types with separate security, health, retry and evidence states.
7. Never put provider keys, browser cookies/storage state, passwords, bearer tokens or private user content in Git, browser bundles, CI artifacts or ordinary logs.
8. Do not bypass CAPTCHA, MFA, security challenges, paywalls or provider restrictions. Stop and request user action when required.
9. Do not launch paid infrastructure, public signup, release publication, destructive migrations or irreversible operations without owner approval.
10. Preserve data through tested, reversible migrations. Enforce workspace/tenant isolation server-side on every read and write.
11. A successful build, health endpoint or mocked test is not proof of a working provider, browser session, Council outcome, parallel isolation or end-to-end integration.
12. Each execution batch must report: files changed, checks run, evidence, remaining limitations and the next batch. Update checkboxes only when verified.
13. Prefer portable containers and cloud-hosted execution. The user's phone is a client, not the deployment or worker host.
14. Keep this plan as the single operational checklist. Supporting architecture and research documents explain decisions; they do not replace execution evidence.

## 1. Confirmed baseline and reuse decisions

### 1.1 Browser Council research already completed

- [x] Inspect candidate projects and selected source/test/license material: Multi-AI Chat Desktop, Yes-Brainer, Synode, Open WebUI, LibreChat, Browser Use, Playwright and Stagehand.
- [x] Record the architecture proposal and implementation roadmap.
- [x] Inspect YJ64 application and Engineering Core integration boundaries read-only.
- [x] Record the current limitations and non-duplication rules.

### 1.2 Existing YJ64 capabilities to integrate or learn from

- Existing model router in `llm_api.py`: do not create a duplicate router merely to call the same configured models.
- Existing message distribution and participant addressing: reuse concepts/contracts where appropriate; Browser Council still owns its own conversation identities and UI.
- Existing chat workspace/history: useful reference, but not a substitute for Browser Council's tenant-safe cloud persistence.
- Existing cloud Council engine: already has independent positions, critique rounds and structured outcomes; Browser Council must add product-grade protocol and evidence semantics rather than reimplementing the same baseline blindly.
- Existing cloud API/worker/queue: durable job IDs, leases, heartbeat, cancellation and recovery are present in the YJ64 application code. Do not build a second copy inside the YJ64 app; decide which parts Browser Council needs for its independent service.
- Existing `yj64.council-api.v1`: compatibility target for external YJ64 integration.
- Browser bridge in the inspected application is placeholder-only; a real Browser Agent remains new work.
- YJ64 server deployment readiness must be revalidated before live integration; source code and CI alone do not prove a deployed worker is accepting real requests.

### 1.3 Browser Council responsibilities

- Independent responsive web/PWA product and workspace UI.
- Tenant-safe users, workspaces, conversations, messages and session history.
- Provider registry supporting API and authorized browser-session adapters.
- Council protocol beyond the existing baseline: explicit phases, dissent, evidence, arbitration, voting and synthesis.
- Research/evidence collection and source contradiction handling.
- Browser Agent with isolated authorized profiles, deterministic actions and verified outcomes.
- Optional compatibility adapter for `yj64.council-api.v1`.
- Product-specific observability, budgets, quotas, retention, backups and deployment packaging.

---

## 2. Phase A — freeze product, legal and interface contracts

**Goal:** remove unresolved decisions that could cause expensive rework before implementation.

### A1. Repository and licensing decisions

1. Reconfirm repository branch, current files, CI and existing license notices.
2. Record the project-license decision or explicitly leave it for owner approval.
3. Define third-party dependency notice and source-reuse policy.
4. Record which audited projects are references only and which components, if any, are approved for reuse.

**Execution evidence:** [Product scope and licensing / reuse policy](PRODUCT_SCOPE_AND_LICENSE_POLICY.md). Repository baseline and absence of a root license/dependency manifest were verified. MVP boundary and reuse restrictions are recorded. The project license remains an owner decision; no license file was added.

### A2. Product scope and resource identities

1. Freeze MVP scope: workspaces, individual API chats, one Council room, streaming, persisted history and cancellation.
2. Define stable IDs: `workspace_id`, `conversation_id`, `participant_id`, `provider_connection_id`, `browser_profile_id`, `run_id`, `turn_id`, `message_id`, `event_id`.
3. Define ownership and tenant boundaries for every resource.
4. Separate execution status (`queued/running/blocked/failed/cancelled/completed`) from analytical outcome (`consensus/qualified_consensus/unresolved_disagreement/insufficient_evidence`).

### A3. API and event contracts

1. Define versioned internal API request/response envelopes.
2. Define event envelope, monotonic sequence/cursor, idempotency and cancellation semantics.
3. Define provider adapter contract for send, stream, cancel, health, timeout and error classification.
4. Define Council run/result schema, including claims, assumptions, evidence references, dissent and limitations.
5. Map the external `yj64.council-api.v1` request/result schema without silently changing it.

**Execution batch A — completed (steps A1.1–A1.4):** branch baseline and existing notices verified; source-reuse and dependency policy recorded; API-first MVP boundary frozen; project-license decision explicitly left for owner approval. Evidence: [PRODUCT_SCOPE_AND_LICENSE_POLICY.md](PRODUCT_SCOPE_AND_LICENSE_POLICY.md).  
**Execution batch B (steps A2.1–A3.5) — validation implementation added:** resource identities, tenant ownership, status/outcome semantics and internal API/event schema are recorded in [API_AND_EVENT_CONTRACTS.md](API_AND_EVENT_CONTRACTS.md) and [browser-council-v1.schema.json](../schemas/browser-council-v1.schema.json). Added Draft 2020-12 validation, representative positive/negative tests, and a read-only snapshot of the external v1 request/status/result constraints. Exact full OpenAPI conformance remains a Phase H gate; the adapter gaps around claim-type conversion and evidence resolution are explicitly documented.  
**Acceptance:** schema and tests pass in GitHub Actions; IDs and ownership are unambiguous; no implementation duplicates existing YJ64 router/queue/Gateway; external v1 mapping gaps remain explicit and are closed by Phase H conformance tests. Current automated workflow result: passed on commit `3079a9774952fa461d6e7c664d9937817080baac` (8 tests passed; GitHub Actions job `json-schema` completed successfully).

---

## 3. Phase B — runnable cloud-first foundation

**Goal:** create a minimal, testable application foundation before implementing product features.

### B1. Repository skeleton

1. Create the agreed web/API/worker structure without adding unnecessary services.
2. Add pinned dependency manifests and reproducible local/container startup.
3. Add environment examples containing placeholders only.
4. Add health/readiness endpoints that distinguish process health from dependency readiness.

### B2. CI and quality gates

1. Add formatting, lint, type checks and unit tests.
2. Add API schema validation and migration checks.
3. Add secret scanning and checks preventing accidental credential fixtures.
4. Add container build and smoke tests.
5. Make CI fail on broken checks; do not treat a green build as feature acceptance.

### B3. Persistence foundation

1. Add PostgreSQL schema for users/workspaces/conversations/messages/runs/events.
2. Add ownership constraints and tenant isolation tests.
3. Add migration/rollback strategy and test fixtures.
4. Add durable event writes and idempotency constraints.

**Execution batch C (B1.1–B2.5) — in progress:** created the initial FastAPI service boundary, liveness/readiness endpoints, pinned API dependencies, Dockerfile and API health tests. CI now runs schema tests, API tests, Python compilation and a container smoke test. Verified on commit `61196e4c4d9ee6b3ae1382ed10943ed7a42da9cb`: all test/build/smoke steps passed.  
**Execution batch D (B3.1–B3.4):** initial schema, tenant isolation, migrations and durable event/idempotency tests.  
**Acceptance:** clean CI; repeatable container startup; schema migrations pass; cross-workspace access tests fail safely; no secrets in repository.

---

## 4. Phase C — API-first individual chats

**Goal:** prove reliable multi-conversation behavior with official model APIs before browser automation.

### C1. Provider registry

1. Implement provider-neutral interface and capability metadata.
2. Add the first two approved API provider adapters.
3. Keep credentials server-side and encrypted at rest.
4. Add connection test, timeout, cancellation and provider error classification.

### C2. Conversation runtime

1. Implement create/list/open/archive conversation operations.
2. Persist user and assistant messages with stable IDs and ordering.
3. Stream responses to the web client using SSE.
4. Support multiple conversations using the same provider without shared mutable context.
5. Add retry only for safe/idempotent operations; reconcile uncertain provider outcomes before resending.

### C3. UI foundation

1. Build responsive workspace/navigation layout.
2. Add individual chat view and participant/provider selector.
3. Add streaming, stop generation, reconnect and visible error states.
4. Add history restore after refresh and sign-in on another device.

**Execution batch E (C1.1–C1.4):** provider interface, two API adapters, server-side secret handling and connection tests.  
**Execution batch F (C2.1–C2.5):** persistence-backed individual chats, SSE streaming, cancellation and same-provider isolation tests.  
**Execution batch G (C3.1–C3.4):** responsive UI, history restore and reconnect behavior.  
**Acceptance:** two independent conversations can call the same provider concurrently; context never crosses; refresh/reconnect restores persisted history; cancellation and provider failures are explicit.

---

## 5. Phase D — Council deliberation engine

**Goal:** deliver a transparent, bounded Council protocol with independently recorded participant contributions.

### D1. Council workspace and execution

1. Create Council profiles and participant roster.
2. Start a run with independent initial positions.
3. Persist each participant execution and result separately.
4. Run independent API participants concurrently with bounded fan-out and per-provider limits.
5. Support cancellation, timeouts, missing participants and partial completion.

### D2. Deliberation phases

1. Implement controlled evidence/context distribution.
2. Implement critique and rebuttal rounds with bounded round count.
3. Implement explicit proposition-level consensus evaluation.
4. Preserve material dissent and unresolved objections.
5. Add optional voting as a separate signal, not a truth oracle.
6. Add arbitration and final synthesis with traceable references to participant positions and evidence.

### D3. Protocol validation

1. Test unanimous agreement, qualified agreement and unresolved disagreement.
2. Test provider timeout/failure and missing responses.
3. Test round-cap exhaustion and cancellation mid-phase.
4. Test that no failure or silence is converted into consensus.
5. Test that final synthesis does not invent evidence or erase dissent.

**Execution batch H (D1.1–D1.5):** Council workspace, parallel independent positions and persisted run records.  
**Execution batch I (D2.1–D2.3):** critique/rebuttal and proposition-level consensus checks.  
**Execution batch J (D2.4–D2.6):** dissent, voting, arbitration and synthesis.  
**Execution batch K (D3.1–D3.5):** protocol edge-case and failure tests.  
**Acceptance:** all phases are persisted and resumable; participant records remain separate; outcome semantics are explicit; tests prove disagreement and failure are not mislabeled as consensus.

---

## 6. Phase E — research and evidence

**Goal:** make research claims traceable to retrieved sources rather than model-generated assertions.

### E1. Search and retrieval adapters

1. Define pluggable search and page-fetch interfaces.
2. Add one initial search provider and one reliable page retrieval path.
3. Store URL, retrieval time, content hash, excerpt/locator and source metadata.
4. Respect robots/access restrictions, rate limits and provider terms.

### E2. Council evidence workflow

1. Support shared evidence packs and optional independent participant research.
2. Bind evidence items to claims and participant messages.
3. Compare source statements and identify contradictions.
4. Distinguish primary sources, secondary reporting, model assertions and test results.
5. Show stale, inaccessible, conflicting or insufficient evidence explicitly.

**Execution batch L (E1.1–E1.4):** search/fetch interfaces and source record schema.  
**Execution batch M (E2.1–E2.5):** evidence packs, claim references, contradiction handling and UI display.  
**Acceptance:** every retrieved factual citation resolves to a stored source record; model assertions are never labeled as retrieved facts; missing/conflicting evidence remains visible.

---

## 7. Phase F — Browser Agent

**Goal:** add authorized browser sessions as a distinct participant connection type, with verified side effects.

### F1. Runtime isolation and profile lifecycle

1. Add isolated Playwright worker containers.
2. Define protected per-user/per-provider browser profile storage.
3. Implement explicit user login/onboarding; never collect passwords through model prompts.
4. Encrypt browser state at rest and restrict worker access.
5. Add profile expiry, revocation and deletion controls.

### F2. Deterministic browser adapter

1. Start with one supported provider website and one authorized profile.
2. Verify domain, profile and login state before acting.
3. Identify the exact target conversation before sending.
4. Send one message and verify it appeared as submitted.
5. Wait for completion and verify the actual response.
6. Store minimal redacted evidence and distinguish observed facts from assumptions.

### F3. Recovery and safety

1. Add adapter health and explicit states: ready, logged_out, challenge_required, blocked, rate_limited, uncertain and failed.
2. Add safe retry/reconciliation; never blindly repeat a possibly submitted message.
3. Stop for CAPTCHA, MFA, unexpected consent or security challenge.
4. Add stop/cancel controls and bounded task budgets.
5. Redact screenshots/traces and never export browser cookies or profile state.

**Execution batch N (F1.1–F1.5):** isolated runtime, encrypted profile storage and lifecycle tests.  
**Execution batch O (F2.1–F2.6):** one provider browser adapter, verified send/receive and evidence records.  
**Execution batch P (F3.1–F3.5):** recovery, stop states, redaction and side-effect safety tests.  
**Acceptance:** a user-authorized session completes a test conversation; submitted messages and completed responses are independently verified; challenge states stop safely; profile data never appears in logs/artifacts.

---

## 8. Phase G — parallel runs and product hardening

**Goal:** support multiple independent Council and browser jobs safely.

### G1. Concurrency and scheduling

1. Define per-tenant concurrency and provider limits.
2. Run multiple independent Council jobs with separate IDs and checkpoints.
3. Prevent mutable browser profile collisions; serialize actions per profile unless safe isolation is proven.
4. Add fair scheduling, bounded retries and cancellation propagation.

### G2. Security and operations

1. Add audit events for authentication, provider use, browser actions and approvals.
2. Add quotas, budgets and retention controls.
3. Add backups and a tested restore procedure.
4. Add metrics, structured logs and redaction.
5. Run threat modeling and access-control tests.

### G3. Product usability

1. Test mobile, tablet and desktop layouts.
2. Add clear connection state, evidence state and run progress.
3. Add export of Council results with citations and dissent.
4. Add onboarding and operational documentation.

**Execution batch Q (G1.1–G1.4):** concurrency controls, independent jobs and profile serialization tests.  
**Execution batch R (G2.1–G2.5):** audit, budgets, retention, backup/restore and security tests.  
**Execution batch S (G3.1–G3.4):** responsive usability, result export and documentation.  
**Acceptance:** concurrent runs cannot read or mutate another workspace's data; worker restart recovers safely; backups restore; quota and audit tests pass.

---

## 9. Phase H — YJ64 integration and portable deployment

**Goal:** allow YJ64 Engineering Core to call Browser Council without coupling the two products.

### H1. Compatibility adapter

1. Implement the exact `yj64.council-api.v1` endpoints and schema.
2. Map authenticated external requests to a preconfigured Council profile.
3. Enforce machine identity, least-privilege scopes, idempotency and owner-scoped status/result/cancel.
4. Return execution status separately from analytical outcome.
5. Preserve evidence references, dissent, assumptions and limitations in results.
6. Add contract tests against the published schema.

### H2. Staging integration

1. Configure a staging machine identity and secrets outside Git.
2. Verify the live Engineering Core Gateway and YJ64 Council API readiness before connecting.
3. Submit, poll, cancel and retrieve a real staging request.
4. Verify the parent system's result handoff and task continuation separately.
5. Keep native YJ-64 Council and Browser Council independently selectable.

### H3. Deployment

1. Package web/API and durable workers in portable containers.
2. Select a free-tier-compatible staging host only after verifying current limits and persistent-worker support.
3. Keep PostgreSQL and object storage portable; document migration to paid/self-hosted infrastructure.
4. Add deployment health checks, backup schedule and rollback instructions.
5. Publish production only after explicit owner approval.

**Execution batch T (H1.1–H1.6):** compatibility adapter and schema/contract tests.  
**Execution batch U (H2.1–H2.5):** staging credentials, readiness check and real end-to-end request lifecycle.  
**Execution batch V (H3.1–H3.5):** portable deployment, verified staging host, backups and rollback.  
**Acceptance:** a real authenticated staging request completes end-to-end; cancellation and result handoff are verified; no neighboring repository is modified; deployment can be moved to another container host without rewriting application logic.

---

## 10. Definition of done

A feature or phase is complete only when:

- [ ] implementation exists in the approved Browser Council branch;
- [ ] relevant unit, integration and security tests pass;
- [ ] CI result and exact commit are recorded;
- [ ] actual runtime behavior is tested where applicable;
- [ ] data isolation, cancellation and recovery are verified where relevant;
- [ ] limitations and unsupported cases are documented;
- [ ] this plan is updated with evidence and next execution batch.

## 11. Current position and next action

**Completed**
- Phase A / Batch A: repository baseline, licensing/reuse policy and MVP boundary.
- Batch B: internal API/event schema, Draft 2020-12 validation and external v1 compatibility snapshot. Contract tests pass.
- Responsive React/TypeScript PWA shell: Council and individual-chat modes, honest local-only draft preview, API status, install icons, offline navigation fallback, Nginx reverse proxy and Compose topology.
- PostgreSQL core schema: workspaces/memberships, provider connection metadata, conversations/messages, councils/participants/runs, durable event counters/events and idempotency records.
- Tenant isolation: workspace-scoped composite foreign keys, RLS policies, and a PostgreSQL CI smoke test proving a non-owner runtime role cannot read or write another principal's workspace.
- API database layer: asyncpg pool lifecycle, readiness connectivity check, transaction-local principal context and safe pooled connection release.
- Authentication boundary: provider-neutral OIDC/JWKS bearer verification, RS256-only validation, required issuer/audience/expiry/subject, fail-closed configuration, issuer-scoped deterministic internal principal IDs.
- First protected API routes: list and create workspaces. Creation atomically creates the owner membership and event counter.
- Full CI passed on `f800f5626d2d6949e768cbe8a1a6ee1eb4f8ca78`: contract/API/auth/workspace tests, Python compilation, PostgreSQL migration + RLS test, PWA build, Compose validation, API/web container builds and API container smoke test.

**Known limitations:** OIDC provider is not configured; no credentials or live sign-in. Database URL and production migration orchestration are not configured in Compose. No workspace membership management, conversation/message endpoints, durable worker, provider adapters, actual model responses, streaming, attachments, evidence search or Browser Agent. The composer remains a local preview. API readiness remains 503 until the worker is implemented.

**Next action:** extend the same verified-principal + tenant-transaction pattern to conversation and message persistence, including idempotency and ordered message history. Only after that connect provider adapters and real streaming; do not display fabricated model answers.
