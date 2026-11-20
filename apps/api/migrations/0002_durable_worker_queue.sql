-- Durable worker queue. Jobs contain identifiers and non-secret execution metadata only.
-- Provider credentials and browser session material must be resolved separately.
BEGIN;

CREATE TABLE worker_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  run_id uuid,
  job_type varchar(80) NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','leased','completed','failed','cancelled')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_owner uuid,
  lease_expires_at timestamptz,
  heartbeat_at timestamptz,
  cancel_requested_at timestamptz,
  last_error_code varchar(80),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, id),
  FOREIGN KEY (workspace_id, run_id)
    REFERENCES council_runs(workspace_id, id) ON DELETE CASCADE,
  CHECK ((status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
      OR (status <> 'leased' AND lease_owner IS NULL AND lease_expires_at IS NULL))
);

CREATE INDEX idx_worker_jobs_ready
  ON worker_jobs(available_at, created_at)
  WHERE status = 'queued';
CREATE INDEX idx_worker_jobs_expired
  ON worker_jobs(lease_expires_at)
  WHERE status = 'leased';
CREATE INDEX idx_worker_jobs_workspace
  ON worker_jobs(workspace_id, created_at DESC);

ALTER TABLE worker_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY worker_jobs_read ON worker_jobs
  FOR SELECT USING (app.is_workspace_member(workspace_id));
CREATE POLICY worker_jobs_insert ON worker_jobs
  FOR INSERT WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner','admin','editor']));
CREATE POLICY worker_jobs_update ON worker_jobs
  FOR UPDATE USING (app.has_workspace_role(workspace_id, ARRAY['owner','admin','editor']))
  WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner','admin','editor']));
CREATE POLICY worker_jobs_delete ON worker_jobs
  FOR DELETE USING (app.has_workspace_role(workspace_id, ARRAY['owner','admin']));

-- A worker can claim across tenants only through this narrow function. It cannot
-- query the queue table directly. SKIP LOCKED prevents duplicate concurrent claims.
CREATE OR REPLACE FUNCTION app.worker_claim_job(p_worker_id uuid, p_lease_seconds integer)
RETURNS TABLE (
  id uuid, workspace_id uuid, run_id uuid, job_type varchar,
  payload jsonb, attempts integer, lease_expires_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, app
SET row_security = off
AS $$
DECLARE claimed_id uuid;
BEGIN
  IF p_worker_id IS NULL OR p_lease_seconds < 15 OR p_lease_seconds > 3600 THEN
    RAISE EXCEPTION 'invalid worker claim parameters' USING ERRCODE = '22023';
  END IF;

  UPDATE public.worker_jobs j
  SET status = 'failed', lease_owner = NULL, lease_expires_at = NULL,
      last_error_code = 'lease_expired_max_attempts', updated_at = now()
  WHERE j.status = 'leased' AND j.lease_expires_at <= now()
    AND j.attempts >= j.max_attempts;

  RETURN QUERY
  WITH candidate AS (
    SELECT j.id
    FROM public.worker_jobs j
    WHERE j.cancel_requested_at IS NULL
      AND j.attempts < j.max_attempts
      AND (
        (j.status = 'queued' AND j.available_at <= now())
        OR (j.status = 'leased' AND j.lease_expires_at <= now())
      )
    ORDER BY j.available_at, j.created_at, j.id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
  )
  UPDATE public.worker_jobs j
  SET status = 'leased', lease_owner = p_worker_id,
      lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      heartbeat_at = now(), attempts = j.attempts + 1, updated_at = now()
  FROM candidate c
  WHERE j.id = c.id
  RETURNING j.id, j.workspace_id, j.run_id, j.job_type,
            j.payload, j.attempts, j.lease_expires_at;
END;
$$;

CREATE OR REPLACE FUNCTION app.worker_heartbeat_job(
  p_job_id uuid, p_worker_id uuid, p_lease_seconds integer
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, app
SET row_security = off
AS $$
DECLARE changed integer;
BEGIN
  IF p_lease_seconds < 15 OR p_lease_seconds > 3600 THEN
    RAISE EXCEPTION 'invalid lease duration' USING ERRCODE = '22023';
  END IF;
  UPDATE public.worker_jobs
  SET heartbeat_at = now(),
      lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      updated_at = now()
  WHERE id = p_job_id AND status = 'leased'
    AND lease_owner = p_worker_id AND cancel_requested_at IS NULL
    AND lease_expires_at > now();
  GET DIAGNOSTICS changed = ROW_COUNT;
  RETURN changed = 1;
END;
$$;

CREATE OR REPLACE FUNCTION app.worker_finish_job(
  p_job_id uuid, p_worker_id uuid, p_succeeded boolean,
  p_error_code varchar DEFAULT NULL, p_retry_delay_seconds integer DEFAULT 30
)
RETURNS varchar
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, app
SET row_security = off
AS $$
DECLARE j public.worker_jobs%ROWTYPE;
DECLARE final_status varchar;
BEGIN
  IF p_retry_delay_seconds < 1 OR p_retry_delay_seconds > 86400 THEN
    RAISE EXCEPTION 'invalid retry delay' USING ERRCODE = '22023';
  END IF;
  SELECT * INTO j FROM public.worker_jobs
  WHERE id = p_job_id AND status = 'leased'
    AND lease_owner = p_worker_id AND lease_expires_at > now()
  FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'lease_lost';
  END IF;

  IF j.cancel_requested_at IS NOT NULL THEN
    final_status := 'cancelled';
  ELSIF p_succeeded THEN
    final_status := 'completed';
  ELSIF j.attempts < j.max_attempts THEN
    UPDATE public.worker_jobs
    SET status = 'queued', available_at = now() + make_interval(secs => p_retry_delay_seconds),
        lease_owner = NULL, lease_expires_at = NULL, heartbeat_at = NULL,
        last_error_code = COALESCE(p_error_code, 'worker_error'), updated_at = now()
    WHERE id = p_job_id;
    RETURN 'queued';
  ELSE
    final_status := 'failed';
  END IF;

  UPDATE public.worker_jobs
  SET status = final_status, lease_owner = NULL, lease_expires_at = NULL,
      heartbeat_at = NULL,
      last_error_code = CASE WHEN final_status = 'failed'
        THEN COALESCE(p_error_code, 'worker_error') ELSE last_error_code END,
      updated_at = now()
  WHERE id = p_job_id;
  RETURN final_status;
END;
$$;

-- Only the dedicated worker role receives function execution. It gets no direct
-- table privileges; deployment must create this NOLOGIN role and grant membership
-- only to the worker process identity.
REVOKE ALL ON FUNCTION app.worker_claim_job(uuid, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.worker_heartbeat_job(uuid, uuid, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.worker_finish_job(uuid, uuid, boolean, varchar, integer) FROM PUBLIC;

COMMIT;
