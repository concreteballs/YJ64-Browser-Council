# Architecture decision proposal

**Status:** Proposed from the Phase 1 source audit. No product code has been implemented yet.  
**Decision principle:** preserve independent product boundaries; reuse verified components; do not duplicate YJ64's existing Gateway.

## 1. Proposed product shape

Build Browser Council as an independent, responsive web application with a server-side API and separately managed workers.

The system has two independent model connection types:

1. **API provider** — a server-side adapter calls an official provider API or an explicitly configured OpenAI-compatible endpoint.
2. **Authorized browser session** — a Browser Agent operates a user-authorized, persistent browser profile and a dedicated page/chat. This is a separate adapter type with its own health, evidence and failure state.

The user can create multiple independent conversations with the same model, multiple councils, and multiple research jobs. The UI displays connection type, participant identity, session state, and whether a result is verified or uncertain.

## 2. Recommended technology composition

| Layer | Proposed choice | Reason |
|---|---|---|
| Web UI | React + TypeScript + responsive PWA | Mature ecosystem, mobile-first web access, installability, and good fit for live streaming chat. |
| HTTP API | FastAPI (Python) | Fits the Python YJ64 Engineering Core environment and existing API/worker integration patterns. |
| Provider adapters | Provider-neutral interface; evaluate LiteLLM SDK for official APIs | Avoid a provider-specific router in the Council core; LiteLLM is MIT and covers many providers. Native adapters can be added when provider-specific search/structured-output features require them. |
| Council orchestration | Explicit, versioned state machine in the first release | The required modes have known phases and invariants. A small deterministic state machine is easier to test than a free-running multi-agent loop. Consider LangGraph later for genuinely branching agent workflows. |
| Durable state | PostgreSQL | Strong transactions, unique idempotency constraints, ownership, event history, queue leases and queryable session isolation. |
| Live updates | Server-Sent Events initially; WebSocket only if bidirectional control requires it | Streaming model output and status events do not require a permanently bidirectional socket. |
| Background execution | Separate Docker worker process(es) | Long model calls, browser tasks, retries and parallel sessions must not run inside short-lived HTTP/edge requests. |
| Browser runtime | Playwright Python, isolated browser context/profile per authorized identity | Deterministic browser operations, authenticated state, per-context isolation, traces and repeatable tests. |
| AI-assisted browser interpretation | Stagehand as optional adapter | Use only when a page cannot be handled reliably with known locators. |
| Autonomous browser research | Browser Use as optional isolated worker | Useful for exploratory navigation, but not the authoritative session or Council state manager. |
| Search | Provider interface with pluggable search/fetch/rerank adapters | Keep search independent from model providers and allow the user to choose shared or per-participant research. |
| Object storage | S3-compatible private bucket | Store evidence bundles, browser traces, screenshots and exports without placing large content in queue rows. |
| Deployment | Docker Compose-compatible services; portable to a VM or container host | Keep cloud vendor choice separate from application logic. |

Do not add Redis, Temporal, Kubernetes or a second orchestration framework before a measured need exists. PostgreSQL can be the first durable queue/state system; Redis can later provide ephemeral pub/sub/cache, not authoritative task state.

## 3. Core service boundaries

### 3.1 Web application

Owns user interaction only: workspaces, model roster, individual chats, Council chat, mode selection, session history, approvals, and display of verified/unverified states. It must not hold long-lived provider secrets in browser JavaScript.

### 3.2 Session and conversation service

Owns stable identities:

- `workspace_id`
- `council_id`
- `conversation_id`
- `participant_id`
- `provider_connection_id`
- `browser_profile_id`
- `browser_session_id`
- `turn_id`
- `message_id`
- `run_id`

Every message, tool call, browser action, event and artifact is bound to its workspace, conversation, turn and run. Never infer the target chat from the currently focused tab or the last active model.

### 3.3 Provider registry

A common interface should cover:

- capability discovery (text, vision, tools, web search, structured output, context size);
- connection type (API or browser);
- send, stream, cancel, health and retry;
- explicit timeouts, output limits, provider error classification and usage/cost data;
- request and response IDs for idempotency/reconciliation.

The provider registry does not decide Council roles or consensus.

### 3.4 Council engine

The engine owns the deliberation protocol, not browser operations or provider-specific HTTP:

- parallel independent positions;
- controlled context release;
- critique and rebuttal rounds;
- consensus evaluation and dissent preservation;
- optional independent voting;
- arbitration;
- final synthesis with claims, evidence, uncertainty and limitations.

Every phase transition is persisted before the next phase begins. Each model call is an individual execution record. A timeout, missing answer, blocked browser, or absent dissent is never converted into consensus.

### 3.5 Browser Agent

Use Playwright as the deterministic driver. Each authorized browser identity gets a separately protected profile. A browser task gets its own run ID and explicit page/tab target. The agent must:

1. verify the intended domain and profile;
2. verify login state without requesting or extracting passwords;
3. navigate only within the user's approved task scope;
4. verify the correct conversation before sending;
5. verify that the message actually appeared as submitted;
6. wait for and verify the completed assistant response;
7. persist a minimal evidence record (timestamps, URL without sensitive query data, adapter version, observed state, result hash);
8. stop visibly for CAPTCHA, MFA, security challenge, unexpected consent, or policy barrier.

No CAPTCHA bypass, anti-bot evasion, paywall bypass, or hidden credential extraction. If a service does not permit the proposed automation, use its official API or mark that browser adapter unsupported.

### 3.6 Research and evidence service

Search, fetch, parse, quote and source validation are independent tools. Every evidence item stores source URL, retrieval time, content hash, relevant excerpt/locator, author/provider where known, and confidence/limitations. Distinguish primary sources, secondary reporting, model assertions and test results. All participants can receive the same evidence pack, or the user can permit independent research.

### 3.7 Durable worker

The worker claims one run under a lease, persists checkpoints and events, renews the lease, observes cancellation and bounded budgets, and can recover after restart. A provider response received but not durably recorded is an uncertain outcome: reconcile before retrying. Browser side effects must never be blindly repeated.

## 4. Deliberation state machine

Suggested common lifecycle:

`created → independent_positions → evidence_collection → critique → revision → consensus_check → (critique | arbitration | synthesis) → completed`

Terminal states include `blocked`, `failed`, `cancelled`, and `timed_out`.

Substantive outcomes are separate from execution status:

- `consensus`
- `qualified_consensus`
- `unresolved_disagreement`
- `insufficient_evidence`

A consensus check must evaluate explicit propositions and material objections. The system must not equate "all models stopped objecting" with a verified truth claim. If the round cap is reached, report remaining disagreement. Voting is independent of consensus and is not a truth oracle.

## 5. API surface

Internal product API (proposal):

- `POST /api/v1/workspaces`
- `POST /api/v1/councils`
- `POST /api/v1/councils/{council_id}/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events` (SSE)
- `POST /api/v1/runs/{run_id}/cancel`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/browser-profiles` (metadata only; browser secret material stays in protected storage)
- `POST /api/v1/provider-connections`

The YJ64-compatible external-agent API is a separate adapter. Do not conflate internal product resources with the narrower external Council contract.

## 6. Session and secret isolation

- Tenant/workspace ownership is enforced on every query, not just at UI routing.
- Provider API keys are encrypted at rest with envelope encryption and a server-side key manager; never store them in client localStorage or logs.
- Browser profile directories and storage-state files are treated as credentials. Encrypt at rest, restrict file-system permissions, isolate workers, and never include profile data in screenshots, artifacts or CI.
- A browser profile must not be mounted into arbitrary user containers. Use per-user/per-provider boundaries and explicit lifecycle/retention controls.
- Multiple API conversations can run concurrently. Browser sessions are additionally serialized per mutable authenticated profile unless the profile is safely cloned and its cookie/session semantics are understood.
- Use request idempotency keys, message IDs, monotonic event sequence numbers, bounded retries and cancellation receipts.

## 7. Commercial architecture

Keep product logic independent from the host:

- stateless web/API container;
- independently scalable browser workers;
- independently scalable API/model workers;
- PostgreSQL as durable system of record;
- private object storage;
- optional Redis for ephemeral coordination.

This permits a small single-user deployment first and a multi-tenant service later. Tenant isolation, quota/budget enforcement, billing and audit logs must be designed before opening multi-user signup.

## 8. Decision summary

**Adopt:** React/TypeScript PWA + FastAPI + PostgreSQL + Docker workers + Playwright Python.  
**Evaluate as optional:** LiteLLM, Stagehand, Browser Use, LangGraph.  
**Use as design references:** LibreChat, Yes-Brainer, Synode, Multi-AI Chat Desktop.  
**Do not adopt as a base:** current Open WebUI for a rebranded commercial SaaS without a licensing exception.  
**Do not build:** a custom browser, a second YJ64 Engineering Core Gateway, or an unbounded autonomous agent loop.
