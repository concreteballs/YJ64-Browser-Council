# YJ64 integration boundary and current state

**Review date:** 2026-11-19  
**Method:** read-only inspection of the public `main` branches and relevant source/docs. No files, branches, settings, secrets or deployments were changed in the other repositories.

## 1. Repositories inspected

- [YJ64 Engineering Core](https://github.com/concreteballs/YJ64-Engineering-Core)
- [YJ-64 application](https://github.com/concreteballs/yj64-clean-bial2modFun5)

This document records the state observed during the audit; it is not a statement that the live service is production-ready.

## 2. Engineering Core already has a Gateway client

The Engineering Core repository already contains:

- `src/yj64_engineering_core/automation/council_gateway.py` — authenticated HTTPS client, protocol validation, request/session identity checks, bounded payloads and result validation;
- `council_tasks.py` — durable submit/poll tasks, checkpoints and result handoff;
- `browser_agent_bridge.py` — versioned `yj64.browser-agent-envelope.v1` envelope and message validation;
- `schemas/council-api-v1.schema.json` — external Council request/result schema;
- `scripts/run_council_gateway_worker.py` and a scheduled worker workflow;
- tests for Gateway client, queue tasks and envelope handling.

The Engineering Core Gateway is a **client/transport adapter**. It does not own model routing or Council deliberation. The Council service owns its own provider participants, turns, outcomes and evidence.

The Gateway integration documentation states that the parent engineering task consumer/runner for `council_result_ready` still needs to be wired to the parent workflow. Therefore a persisted result handoff must not be described as automatic end-to-end parent-task resumption.

## 3. Existing YJ-64 application cloud Council work

The application repository currently contains a significant amount of new cloud API/worker work that was not reflected in older integration notes:

- `supabase/functions/council-api/index.ts` — Supabase Edge Function API ingress;
- `docs/openapi/council-api-v1.yaml` — OpenAPI contract and deployed Edge Function base URL;
- Supabase migrations for machine agents, request ownership, idempotency, queue state, events and worker registry;
- `cloud_worker/engine.py` — server-side Council engine adapter that calls the existing central `llm_api.generate_response` router using server-injected route configuration;
- `cloud_worker/worker.py` and `queue_store.py` — separate worker process, leases, cancellation, heartbeat and Supabase/PostgreSQL queue adapters;
- Dockerfile, Compose configuration and deployment instructions;
- API smoke tests and cloud-worker tests.

The application design correctly keeps Android as a client, not a long-running public API server. The Edge Function is the short-request ingress; the long-running Council worker is a separate container.

### Readiness status observed in source and deployment instructions

- The Edge Function ingress is deployed and has a health/readiness contract.
- The API smoke workflow explicitly expects `ready_for_requests=false`, `council_engine=not_connected`, and `worker=not_deployed`.
- The cloud worker is prepared and CI-tested, but the deployment guide says no external worker host has yet been selected/deployed.
- The submission gate must remain closed until a live worker heartbeat, real provider E2E run, cancellation, lease recovery and terminal-result persistence have been verified.
- The worker engine documentation says weighted voting is not implemented; it must report that limitation rather than fabricate weighted results.
- The worker's current council protocol is a bounded implementation of independent positions, critique rounds and structured outcomes. It explicitly does not treat model agreement as external factual verification.

This is a critical distinction: **API ingress exists, but the full live Council service is not yet ready for accepted production requests.** A successful API health check or GitHub Actions run is not proof of a live multi-model session.

## 4. Integration decision for Browser Council

Browser Council must remain an independent product and must not replace or rewrite the existing YJ-64 application Council or Engineering Core Gateway.

Recommended boundary:

1. Browser Council implements its own internal workspace, conversation, provider, browser-profile and Council-run APIs.
2. Browser Council additionally exposes a compatibility adapter for `yj64.council-api.v1`:
   - `POST /api/v1/external-agents/council/requests`
   - `GET /api/v1/external-agents/council/requests/{request_id}`
   - `GET /api/v1/external-agents/council/requests/{request_id}/result`
   - `POST /api/v1/external-agents/council/requests/{request_id}/cancel`
3. The v1 adapter maps an authenticated YJ64 request to a preconfigured Council profile and returns the exact status/outcome/result shape expected by Engineering Core.
4. Do not silently extend or change the existing v1 schema. If Engineering Core later needs caller-selected participants, provider connection IDs, or browser-session selection, propose a backward-compatible `yj64.council-api.v2` with explicit fields and tests.
5. Engineering Core remains responsible for its own durable queue, task lease, parent-task checkpoint and evidence-based acceptance of returned results.
6. The YJ64 Android application remains independently responsible for its native/local chat UI and its own cloud API/worker readiness.

This permits the user to choose between the native YJ-64 Council and Browser Council without automatically splitting tasks or merging the two state stores.

## 5. Ownership and non-duplication matrix

| Capability | Owner |
|---|---|
| Browser Council workspaces, provider connections and browser profiles | Browser Council |
| Browser Council independent chats and Council sessions | Browser Council |
| Browser Council Consensus/Critique/Voting/Synthesis lifecycle | Browser Council |
| Browser automation and provider UI adapters | Browser Council Browser Agent |
| Native YJ-64 app participant router and native Council runtime | YJ-64 application |
| YJ-64 application cloud ingress and worker | YJ-64 application |
| Durable Engineering Core parent task and submit/poll Gateway client | YJ64 Engineering Core |
| Engineering task continuation and acceptance of returned evidence | YJ64 Engineering Core |

## 6. Security contract

- Browser Council issues a separate machine identity for each external integration; scopes are least-privilege.
- Bearer credentials remain server-side in secret managers. No token in the Android app, browser bundle, GitHub files, queue payloads or logs.
- All status/result/cancel operations are owner-scoped.
- Idempotency binds the authenticated agent to a canonical payload hash. Same key + same payload returns the same request; same key + different payload returns conflict.
- The API distinguishes execution status from substantive outcome.
- The returned result includes dissent, unresolved questions, evidence references, assumptions and limitations.
- Council text is untrusted analytical input, not executable instructions and not authority to override Engineering Core permissions.

## 7. Source references

- https://github.com/concreteballs/YJ64-Engineering-Core/blob/main/docs/COUNCIL_GATEWAY_INTEGRATION.md
- https://github.com/concreteballs/YJ64-Engineering-Core/blob/main/src/yj64_engineering_core/automation/council_gateway.py
- https://github.com/concreteballs/YJ64-Engineering-Core/blob/main/src/yj64_engineering_core/automation/council_tasks.py
- https://github.com/concreteballs/yj64-clean-bial2modFun5/blob/main/docs/ADR-001-COUNCIL-API-CLOUD-RUNTIME.md
- https://github.com/concreteballs/yj64-clean-bial2modFun5/blob/main/docs/COUNCIL-API-IMPLEMENTATION-AUDIT.md
- https://github.com/concreteballs/yj64-clean-bial2modFun5/blob/main/cloud_worker/DEPLOYMENT.md
- https://github.com/concreteballs/yj64-clean-bial2modFun5/blob/main/cloud_worker/README.md
- https://github.com/concreteballs/yj64-clean-bial2modFun5/blob/main/.github/workflows/council-api-smoke.yml

## 8. Explicit non-actions

No modifications were made to either inspected YJ64 repository. Browser Council changes remain confined to `concreteballs/YJ64-Browser-Council`.
