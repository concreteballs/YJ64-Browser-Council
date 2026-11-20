#!/usr/bin/env bash
set -euo pipefail

container="browser-council-postgres-ci"
docker rm -f "$container" >/dev/null 2>&1 || true
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$container" \
  -e POSTGRES_PASSWORD=ci-only-password \
  -p 127.0.0.1:55432:5432 \
  postgres:16-alpine >/dev/null

ready=0
for attempt in $(seq 1 30); do
  if docker exec "$container" pg_isready -U postgres >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" != "1" ]]; then
  docker logs "$container"
  exit 1
fi

docker exec "$container" psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  -c "CREATE ROLE browser_council_runtime NOLOGIN"
docker exec -i "$container" psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  < apps/api/migrations/0001_workspace_core.sql
docker exec -i "$container" psql -v ON_ERROR_STOP=1 -U postgres -d postgres <<'SQL'
GRANT USAGE ON SCHEMA public, app TO browser_council_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO browser_council_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO browser_council_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO browser_council_runtime;
SQL

docker exec -i "$container" psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  < tests/db/rls_smoke.sql
echo "PostgreSQL migration and tenant RLS smoke test passed."
