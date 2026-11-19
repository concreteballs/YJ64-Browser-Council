# Browser Council internal API and event contracts

**Contract:** `browser-council.internal.v1`  
**Schema:** [browser-council-v1.schema.json](../schemas/browser-council-v1.schema.json)  
**External compatibility target:** `yj64.council-api.v1` (unchanged)  
**Status:** Batch B contract baseline; implementation and generated OpenAPI are not yet claimed.

## 1. Contract separation

Browser Council has its own product API and event stream. The external YJ64 machine-to-machine API is a compatibility adapter, not the internal data model. Internal changes must not silently alter the published `yj64.council-api.v1` request, response, status, authentication, or route semantics.

All routes below are versioned under `/api/v1`. Authentication is session/token based; authorization is enforced server-side on every resource access.

## 2. Stable resource identities

Every resource receives a server-generated opaque ID matching the schema's ID grammar. IDs are immutable and never reused.

| Resource | ID | Ownership / scope |
|---|---|---|
| User | `user_id` | Authentication principal |
| Workspace | `workspace_id` | Owned by a user/tenant; root isolation boundary |
| Council | `council_id` | Belongs to one workspace |
| Conversation | `conversation_id` | Belongs to one workspace; individual chat |
| Participant | `participant_id` | Roster member in a Council; references a connection |
| Provider connection | `provider_connection_id` | Belongs to one workspace; API or browser-session type |
| Browser profile | `browser_profile_id` | Belongs to one workspace and one authorized browser identity |
| Browser session | `browser_session_id` | Belongs to one browser profile and worker lease |
| Run | `run_id` | Belongs to one workspace and one conversation/Council execution |
| Turn | `turn_id` | One user/model exchange within a conversation or run |
| Message | `message_id` | Belongs to one conversation/turn and has an immutable author |
| Event | `event_id` | Immutable event record; sequence scoped to workspace |
| Artifact | `artifact_id` | Private object-storage item owned by a workspace |

A child resource cannot be moved across workspaces by changing a client-supplied parent ID. The server derives ownership from the authenticated principal and verifies the complete parent chain. Cross-workspace references return a non-disclosing not-found/forbidden response.

## 3. Execution status versus analytical outcome

Execution status answers whether work ran. Analytical outcome answers what the Council concluded. They are independent fields.

**Execution status:** `queued`, `running`, `blocked`, `failed`, `cancelled`, `completed`.

**Analytical outcome:** `consensus`, `qualified_consensus`, `unresolved_disagreement`, `insufficient_evidence`; nullable until a completed analysis exists.

Rules:
- `blocked`, `failed`, `cancelled` and `queued/running` do not carry a final analytical outcome.
- A completed run must carry an analytical outcome, including `insufficient_evidence` when appropriate.
- Missing participants, timeouts, provider failures, empty responses and round-cap exhaustion cannot be represented as consensus.
- Voting is a separate signal and never overwrites the analytical outcome.
- A result preserves participant positions, material dissent, claim types, evidence references, assumptions and limitations.

## 4. Internal API surface

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/workspaces` | Create workspace |
| GET | `/api/v1/workspaces` | List caller-owned workspaces |
| GET | `/api/v1/workspaces/{workspace_id}` | Read owned workspace |
| POST | `/api/v1/workspaces/{workspace_id}/provider-connections` | Create API/browser connection metadata |
| GET | `/api/v1/workspaces/{workspace_id}/provider-connections` | List safe connection metadata |
| POST | `/api/v1/workspaces/{workspace_id}/conversations` | Create individual conversation |
| GET | `/api/v1/conversations/{conversation_id}/messages` | Read persisted history |
| POST | `/api/v1/conversations/{conversation_id}/messages` | Submit message (idempotent) |
| POST | `/api/v1/conversations/{conversation_id}/turns/{turn_id}/cancel` | Cancel active generation |
| POST | `/api/v1/workspaces/{workspace_id}/councils` | Create Council profile |
| POST | `/api/v1/councils/{council_id}/runs` | Start Council run (idempotent) |
| GET | `/api/v1/runs/{run_id}` | Read run status/result |
| GET | `/api/v1/runs/{run_id}/events` | Replay/stream events (SSE) |
| POST | `/api/v1/runs/{run_id}/cancel` | Request cancellation |
| GET | `/api/v1/health/live` | Process liveness |
| GET | `/api/v1/health/ready` | Dependency readiness |

Create-message and create-run requests require an `Idempotency-Key`. Same key + same canonical request returns the original operation; same key + different request returns `409 Conflict`. The server persists the accepted operation before returning `202 Accepted`.

## 5. Event envelope and ordering

Every persisted event follows the schema's `event` definition and contains:
- immutable `event_id`;
- `workspace_id` and strictly increasing workspace-scoped `sequence`;
- event type and UTC `occurred_at`;
- explicit resource references;
- optional `correlation_id` (whole user request) and `causation_id` (event/action that caused this event);
- typed-by-event `payload`.

SSE event IDs use the durable sequence/cursor. Reconnect with `Last-Event-ID` replays events after that cursor. A client must tolerate duplicate delivery and deduplicate by `event_id`/sequence. Sequence gaps trigger replay; clients must not infer missing events. Persist the event and state transition atomically before publishing it.

The server may emit token deltas for UI streaming, but durable message completion is a distinct event. A partial stream is not a completed assistant message.

## 6. Provider adapter contract

An adapter declares `connection_type` as exactly one of:
- `api`: official provider API or explicitly configured compatible endpoint;
- `browser_session`: user-authorized browser profile operated by the isolated Browser Agent.

Both expose capability metadata, health, send/stream, cancel and typed errors. They do not share credential storage or retry semantics.

API credentials are stored as opaque secret-manager references; never return secret values. Browser profile material is credential-equivalent and remains in encrypted, isolated storage. Browser actions require a profile ID and explicit target page/conversation. Uncertain send outcomes are reconciled before retry; no blind resend.

## 7. Cancellation, retries and idempotency

- Cancellation is a request, not an assertion that work stopped. Return the observed state and emit a terminal event only after the worker confirms the stop.
- Idempotency is scoped to authenticated workspace/principal + operation + key and binds a canonical payload hash.
- Retry only operations known to be safe. A provider call or browser send with uncertain side effects must be reconciled first.
- Every worker lease and model/browser operation references its run/turn/message IDs.
- A terminal execution state is immutable; recovery creates a new run rather than reopening a terminal one.

## 8. Mapping to `yj64.council-api.v1`

The adapter exposes only the already published external operations:
- `POST /api/v1/external-agents/council/requests`
- `GET /api/v1/external-agents/council/requests/{request_id}`
- `GET /api/v1/external-agents/council/requests/{request_id}/result`
- `POST /api/v1/external-agents/council/requests/{request_id}/cancel`

Mapping rules:
1. External `agent_id` authenticates/identifies the machine caller; it is not an internal `user_id`.
2. `correlation_id` is retained as correlation metadata; the adapter generates its own internal `run_id` and event IDs.
3. External `idempotency_key` is preserved and bound to the canonical external payload hash.
4. External `task.title`, `task.prompt`, `task.context`, `task.evidence_refs`, `mode`, `limits` and `voting` map into a preconfigured Council profile and one internal run. Caller-supplied text is untrusted data, never privileged instructions.
5. External `request_id` and `session_id` map to stable adapter records; they are not aliases for internal `run_id` or `conversation_id`.
6. Internal execution states map to the exact external status enum. The adapter returns a result only when completed; blocked/failed/cancelled are not fabricated as completed results.
7. Internal outcomes map only to the four external outcome values. Additional internal detail is preserved in supported result fields, not by adding unrecognized v1 fields.
8. Authentication, route paths, required headers, request/result shapes and status codes remain governed by the external OpenAPI/schema documents. No v1 extension is introduced here.

## 9. Explicit limitations / next validation

- This is a contract baseline, not a running API or proof of schema conformance.
- The schema describes representative request/event/result structures; route-specific request/response wrappers and generated OpenAPI will be added with the runnable API foundation.
- Validate the internal schema with a JSON Schema 2020-12 validator in CI before implementation is accepted.
- Validate external request/result examples against the exact Engineering Core schema and application OpenAPI without modifying either source repository.
- Owner approval is still required for project source license and commercial distribution terms.
