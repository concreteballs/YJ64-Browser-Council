-- Browser Council core persistence, PostgreSQL 16+.
-- Authentication identities are external to this schema; user_id is the stable UUID
-- issued by the configured identity provider. Never accept it from request JSON.
BEGIN;

CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

CREATE TABLE IF NOT EXISTS workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(120) NOT NULL CHECK (length(trim(name)) > 0),
  description varchar(2000) NOT NULL DEFAULT '',
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspace_members (
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  role varchar(16) NOT NULL CHECK (role IN ('owner','admin','editor','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, user_id)
);

CREATE OR REPLACE FUNCTION app.is_workspace_member(target_workspace uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = target_workspace
      AND m.user_id = app.current_user_id()
  )
$$;

CREATE OR REPLACE FUNCTION app.has_workspace_role(target_workspace uuid, allowed_roles text[])
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = target_workspace
      AND m.user_id = app.current_user_id()
      AND m.role = ANY(allowed_roles)
  )
$$;

CREATE OR REPLACE FUNCTION app.is_workspace_creator(target_workspace uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off
AS 'SELECT EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = target_workspace AND w.created_by = app.current_user_id())';

CREATE TABLE IF NOT EXISTS provider_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name varchar(120) NOT NULL,
  provider varchar(80) NOT NULL,
  connection_type varchar(24) NOT NULL CHECK (connection_type IN ('api','browser_session')),
  secret_reference text,
  status varchar(24) NOT NULL DEFAULT 'unconfigured'
    CHECK (status IN ('unconfigured','active','degraded','revoked')),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, id),
  CHECK (secret_reference IS NULL OR length(secret_reference) <= 512)
);

CREATE TABLE IF NOT EXISTS conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title varchar(300) NOT NULL,
  provider_connection_id uuid,
  system_instructions text NOT NULL DEFAULT '',
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, id),
  FOREIGN KEY (workspace_id, provider_connection_id)
    REFERENCES provider_connections(workspace_id, id)
);

CREATE TABLE IF NOT EXISTS messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  conversation_id uuid NOT NULL,
  turn_id uuid,
  role varchar(24) NOT NULL CHECK (role IN ('system','user','assistant','tool')),
  content text NOT NULL CHECK (length(content) <= 100000),
  status varchar(24) NOT NULL DEFAULT 'completed'
    CHECK (status IN ('queued','streaming','completed','failed','cancelled')),
  sequence bigint NOT NULL CHECK (sequence > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (workspace_id, conversation_id)
    REFERENCES conversations(workspace_id, id) ON DELETE CASCADE,
  UNIQUE (conversation_id, sequence),
  UNIQUE (workspace_id, id)
);

CREATE TABLE IF NOT EXISTS councils (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name varchar(120) NOT NULL,
  description varchar(2000) NOT NULL DEFAULT '',
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, id)
);

CREATE TABLE IF NOT EXISTS council_participants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  council_id uuid NOT NULL,
  provider_connection_id uuid NOT NULL,
  display_name varchar(120) NOT NULL,
  model_identifier varchar(160),
  position integer NOT NULL CHECK (position >= 0),
  enabled boolean NOT NULL DEFAULT true,
  FOREIGN KEY (workspace_id, council_id)
    REFERENCES councils(workspace_id, id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id, provider_connection_id)
    REFERENCES provider_connections(workspace_id, id),
  UNIQUE (council_id, position),
  UNIQUE (workspace_id, id)
);

CREATE TABLE IF NOT EXISTS council_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  council_id uuid NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','blocked','failed','cancelled','completed')),
  outcome varchar(32)
    CHECK (outcome IN ('consensus','qualified_consensus','unresolved_disagreement','insufficient_evidence')),
  prompt text NOT NULL CHECK (length(prompt) BETWEEN 1 AND 50000),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (workspace_id, council_id)
    REFERENCES councils(workspace_id, id),
  UNIQUE (workspace_id, id),
  CHECK ((status = 'completed' AND outcome IS NOT NULL)
      OR (status <> 'completed' AND outcome IS NULL))
);

CREATE TABLE IF NOT EXISTS workspace_event_counters (
  workspace_id uuid PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
  last_sequence bigint NOT NULL DEFAULT 0 CHECK (last_sequence >= 0)
);

CREATE TABLE IF NOT EXISTS workspace_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  sequence bigint NOT NULL CHECK (sequence > 0),
  event_type varchar(100) NOT NULL,
  resource jsonb NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, sequence)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  principal_id uuid NOT NULL,
  operation varchar(120) NOT NULL,
  idempotency_key varchar(256) NOT NULL,
  request_hash char(64) NOT NULL,
  response_status integer,
  response_body jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
  UNIQUE (workspace_id, principal_id, operation, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id, workspace_id);
CREATE INDEX IF NOT EXISTS idx_conversations_workspace_updated ON conversations(workspace_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_sequence ON messages(conversation_id, sequence);
CREATE INDEX IF NOT EXISTS idx_council_runs_workspace_created ON council_runs(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_events_replay ON workspace_events(workspace_id, sequence);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry ON idempotency_records(expires_at);

-- Enable row-level security on every tenant-owned relation.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'workspaces','workspace_members','provider_connections','conversations',
    'messages','councils','council_participants','council_runs',
    'workspace_event_counters','workspace_events','idempotency_records'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    
  END LOOP;
END $$;

CREATE POLICY workspace_read ON workspaces
  FOR SELECT USING (app.is_workspace_member(id));
CREATE POLICY workspace_create ON workspaces
  FOR INSERT WITH CHECK (created_by = app.current_user_id());
CREATE POLICY workspace_update ON workspaces
  FOR UPDATE USING (app.has_workspace_role(id, ARRAY['owner','admin']))
  WITH CHECK (app.has_workspace_role(id, ARRAY['owner','admin']));

CREATE POLICY membership_read ON workspace_members
  FOR SELECT USING (user_id = app.current_user_id() OR app.is_workspace_member(workspace_id));
CREATE POLICY membership_create ON workspace_members
  FOR INSERT WITH CHECK (
    (user_id = app.current_user_id() AND app.is_workspace_creator(workspace_id))
    OR app.has_workspace_role(workspace_id, ARRAY['owner','admin'])
  );
CREATE POLICY membership_update ON workspace_members
  FOR UPDATE USING (app.has_workspace_role(workspace_id, ARRAY['owner','admin']))
  WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner','admin']));
CREATE POLICY membership_delete ON workspace_members
  FOR DELETE USING (app.has_workspace_role(workspace_id, ARRAY['owner','admin']));

-- Common tenant isolation policy. Writes require editor/admin/owner membership.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'provider_connections','conversations','messages','councils',
    'council_participants','council_runs','workspace_event_counters',
    'workspace_events','idempotency_records'
  ] LOOP
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR SELECT USING (app.is_workspace_member(workspace_id))',
      t || '_read', t
    );
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR INSERT WITH CHECK (app.has_workspace_role(workspace_id, ARRAY[''owner'',''admin'',''editor'']))',
      t || '_insert', t
    );
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR UPDATE USING (app.has_workspace_role(workspace_id, ARRAY[''owner'',''admin'',''editor''])) WITH CHECK (app.has_workspace_role(workspace_id, ARRAY[''owner'',''admin'',''editor'']))',
      t || '_update', t
    );
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR DELETE USING (app.has_workspace_role(workspace_id, ARRAY[''owner'',''admin'']))',
      t || '_delete', t
    );
  END LOOP;
END $$;

COMMIT;
