# API database lifecycle

The API uses an asyncpg connection pool configured through `DATABASE_URL`.
When configured, the FastAPI lifespan opens the pool and closes it during
shutdown. The liveness endpoint remains process-only.

A tenant-scoped operation must use
`Database.tenant_transaction(principal_id)`. This starts a database
transaction and sets `app.user_id` with PostgreSQL `set_config(..., true)`,
which is transaction-local and cannot leak through a pooled connection after
commit/rollback. The principal UUID must come only from a verified
authentication dependency; this repository has not selected or implemented
an identity provider yet.

The readiness endpoint verifies database connectivity but intentionally
remains HTTP 503 while the durable worker is not implemented. A reachable
database alone does not mean the service can safely accept model work.

## Migration and runtime roles

Apply migrations using a dedicated migration-owner role. The API must connect
using a separate non-owner role with no superuser or `BYPASSRLS` privilege.
Grant only the schema, table, sequence and function permissions it needs.
Never run the API as the migration owner or a PostgreSQL superuser.

The initial migration is currently applied explicitly by the CI database
smoke test. Production migration orchestration and secret provisioning are
not implemented; do not treat this connection layer as a production-ready
deployment.
