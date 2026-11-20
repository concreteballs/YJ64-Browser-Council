# Provider, conversation and message API v1

The current API exposes workspace-scoped provider metadata and conversations,
plus conversation-scoped ordered message history.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/workspaces/{workspace_id}/provider-connections` | List provider metadata |
| POST | `/api/v1/workspaces/{workspace_id}/provider-connections` | Register an unconfigured API/browser-session connection |
| GET | `/api/v1/workspaces/{workspace_id}/conversations` | List conversations |
| POST | `/api/v1/workspaces/{workspace_id}/conversations` | Create conversation and sequence counter |
| GET | `/api/v1/conversations/{conversation_id}/messages` | Read ordered message history |
| POST | `/api/v1/conversations/{conversation_id}/messages` | Persist a user message idempotently |

All routes require verified OIDC identity and a tenant-scoped database
transaction. Workspace ownership is enforced by PostgreSQL RLS and
workspace-scoped foreign keys.

## Provider connection safety

The create route stores only display/provider metadata and the connection type
(`api` or `browser_session`). New connections remain `unconfigured`.
It does not accept API keys, cookies, browser storage state or other secrets.
Secret-manager integration and provider health checks are not implemented.

## Message write semantics

Message creation requires both a body `idempotency_key` and matching
`Idempotency-Key` header. The server hashes the canonical client message ID
and content. A repeated key with the same request returns the stored response;
the same key with a different request returns 409. The idempotency insert uses
the unique tenant/principal/operation/key constraint and `ON CONFLICT DO
NOTHING`, then locks and reads the existing record to handle concurrent
retries safely.

A per-conversation counter row is incremented under the same transaction,
providing a strictly ordered message sequence. The user message, durable
`message.created` event, and idempotency response are committed atomically.
The API does not enqueue an AI request yet; a persisted user message is not
represented as an assistant response.

## Deliberate limits

Provider secrets/adapters, actual model calls, assistant messages, streaming,
cancellation, event replay/SSE, attachments, pagination cursors and worker
execution remain future work. Message history currently uses a bounded
sequence/limit query.
