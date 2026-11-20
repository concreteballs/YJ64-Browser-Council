# Data model and tenant isolation

**Status:** initial PostgreSQL migration drafted; not yet connected to the API runtime.

## Isolation boundary

A workspace is the tenant boundary. Every workspace-owned row carries
`workspace_id`; child relationships use composite foreign keys containing
that workspace ID so a child cannot reference a parent in another tenant.
Authorization is not inferred from a client-supplied workspace ID.

The API must authenticate the request first, derive the stable principal UUID
from the verified identity, then set `app.user_id` transaction-locally
(`SET LOCAL app.user_id = ...`) on the same database transaction used for
the query. Never set it from request JSON, query parameters, or unverified
headers. Connection-pool code must use transaction-local settings and always
rollback/return the connection safely.

The runtime database role must not own the tables, be a superuser, or have
`BYPASSRLS`. It receives only required table/sequence/function grants.
Migrations run under a separate owner role. RLS is enabled and forced on
tenant tables. The helper functions are narrowly scoped SECURITY DEFINER
membership checks with a fixed search_path; do not add dynamic SQL to them.

## Initial entities

- Workspaces and membership roles: owner, admin, editor, viewer.
- Provider connection metadata: API and browser-session types remain distinct.
  Only an opaque secret-manager reference may be stored here; never plaintext
  API keys, cookies, browser storage state or session tokens.
- Conversations and ordered messages.
- Council profiles and ordered participants.
- Council runs with separate execution status and analytical outcome. A
  completed run requires an outcome; non-completed runs cannot carry one.
- Workspace event sequence/counter and durable event records.
- Idempotency records bound to principal, operation, key and request hash.

## Deliberate omissions

No user/password table: identity is delegated to an authentication provider.
No credential material or browser cookies: a future encrypted secret service
must own those. No artifact bytes: use private object storage with scoped
authorization. No worker lease table yet; it belongs with the durable queue
implementation, not the first persistence migration.

## Migration

Apply `apps/api/migrations/0001_workspace_core.sql` with a migration-owner
role. Do not run it as the application runtime role.

The CI database test creates a separate non-owner runtime role and verifies
that a second principal cannot read another workspace's conversation rows.
This is a baseline regression test, not a complete penetration test or
substitute for API authorization tests.
