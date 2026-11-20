# Workspace API v1

Implemented routes:

| Method | Route | Behavior |
|---|---|---|
| GET | `/api/v1/workspaces` | List only workspaces visible through the caller's RLS membership |
| POST | `/api/v1/workspaces` | Create workspace, owner membership and event sequence counter atomically |

Both routes require a verified OIDC bearer token. The API maps the verified
issuer+subject to an internal UUIDv5 principal and starts a transaction using
`Database.tenant_transaction`; the transaction-local principal is then
enforced by PostgreSQL RLS.

The create operation inserts the workspace, owner membership and initial
workspace event counter in one transaction. If any step fails, all changes
roll back. Workspace names are trimmed and validated; descriptions are capped
at 2,000 characters.

Example request:

```http
POST /api/v1/workspaces
Authorization: Bearer <OIDC access token>
Content-Type: application/json

{
  "name": "Research workspace",
  "description": "Independent analysis"
}
```

The response contains the workspace ID, name, description and timestamps.
The API never accepts a user ID or membership role from the request body.

## Not yet implemented

Workspace detail/update/delete, invitation and membership management,
conversation/message CRUD, provider connection management, council/run
endpoints, pagination and rate limits. These must use the same principal +
transaction + RLS path and must not trust client-supplied tenant ownership.
