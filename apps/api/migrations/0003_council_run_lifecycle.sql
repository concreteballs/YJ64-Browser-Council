-- Worker-owned Council run transitions and validated finalization.
BEGIN;

ALTER TABLE public.council_runs
  ADD COLUMN IF NOT EXISTS result jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS idx_worker_jobs_one_per_run
  ON public.worker_jobs(run_id) WHERE run_id IS NOT NULL;

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
DECLARE claimed public.worker_jobs%ROWTYPE;
DECLARE changed integer;
DECLARE event_sequence bigint;
BEGIN
  IF p_worker_id IS NULL OR p_lease_seconds < 15 OR p_lease_seconds > 3600 THEN
    RAISE EXCEPTION 'invalid worker claim parameters' USING ERRCODE = '22023';
  END IF;

  UPDATE public.worker_jobs j
  SET status = 'cancelled', lease_owner = NULL, lease_expires_at = NULL,
      heartbeat_at = NULL, updated_at = now()
  WHERE j.status = 'leased' AND j.cancel_requested_at IS NOT NULL
    AND j.lease_expires_at <= now();

  UPDATE public.council_runs r
  SET status = 'cancelled', updated_at = now()
  FROM public.worker_jobs j
  WHERE j.run_id = r.id AND j.workspace_id = r.workspace_id
    AND j.status = 'cancelled' AND j.cancel_requested_at IS NOT NULL
    AND r.status IN ('queued','running');

  UPDATE public.worker_jobs j
  SET status = 'failed', lease_owner = NULL, lease_expires_at = NULL,
      heartbeat_at = NULL, last_error_code = 'lease_expired_max_attempts',
      updated_at = now()
  WHERE j.status = 'leased' AND j.lease_expires_at <= now()
    AND j.attempts >= j.max_attempts;

  UPDATE public.council_runs r
  SET status = 'failed', updated_at = now()
  FROM public.worker_jobs j
  WHERE j.run_id = r.id AND j.workspace_id = r.workspace_id
    AND j.status = 'failed' AND j.last_error_code = 'lease_expired_max_attempts'
    AND r.status IN ('queued','running');

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
  RETURNING j.* INTO claimed;

  IF NOT FOUND THEN
    RETURN;
  END IF;

  IF claimed.job_type = 'council.run' AND claimed.run_id IS NOT NULL THEN
    UPDATE public.council_runs
    SET status = 'running', updated_at = now()
    WHERE id = claimed.run_id AND workspace_id = claimed.workspace_id
      AND status = 'queued';
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed = 1 THEN
      UPDATE public.workspace_event_counters
      SET last_sequence = last_sequence + 1
      WHERE workspace_id = claimed.workspace_id
      RETURNING last_sequence INTO event_sequence;
      IF event_sequence IS NULL THEN
        RAISE EXCEPTION 'workspace event counter is missing';
      END IF;
      INSERT INTO public.workspace_events
        (workspace_id, sequence, event_type, resource, payload)
      VALUES (
        claimed.workspace_id, event_sequence, 'council_run.started',
        jsonb_build_object('workspace_id', claimed.workspace_id,
                           'run_id', claimed.run_id, 'job_id', claimed.id),
        jsonb_build_object('status', 'running', 'attempt', claimed.attempts)
      );
    END IF;
  END IF;

  RETURN QUERY SELECT claimed.id, claimed.workspace_id, claimed.run_id,
                      claimed.job_type, claimed.payload, claimed.attempts,
                      claimed.lease_expires_at;
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
DECLARE event_sequence bigint;
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

  IF p_succeeded AND j.job_type = 'council.run' AND j.run_id IS NOT NULL THEN
    RETURN 'completion_required';
  ELSIF j.cancel_requested_at IS NOT NULL THEN
    final_status := 'cancelled';
  ELSIF p_succeeded THEN
    final_status := 'completed';
  ELSIF j.attempts < j.max_attempts THEN
    UPDATE public.worker_jobs
    SET status = 'queued', available_at = now() + make_interval(secs => p_retry_delay_seconds),
        lease_owner = NULL, lease_expires_at = NULL, heartbeat_at = NULL,
        last_error_code = COALESCE(p_error_code, 'worker_error'), updated_at = now()
    WHERE id = p_job_id;
    IF j.run_id IS NOT NULL THEN
      UPDATE public.council_runs SET status = 'queued', updated_at = now()
      WHERE id = j.run_id AND workspace_id = j.workspace_id AND status = 'running';
    END IF;
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

  IF j.run_id IS NOT NULL THEN
    UPDATE public.council_runs
    SET status = final_status, updated_at = now()
    WHERE id = j.run_id AND workspace_id = j.workspace_id
      AND status IN ('queued','running');
    UPDATE public.workspace_event_counters
    SET last_sequence = last_sequence + 1
    WHERE workspace_id = j.workspace_id
    RETURNING last_sequence INTO event_sequence;
    IF event_sequence IS NULL THEN
      RAISE EXCEPTION 'workspace event counter is missing';
    END IF;
    INSERT INTO public.workspace_events
      (workspace_id, sequence, event_type, resource, payload)
    VALUES (
      j.workspace_id, event_sequence,
      CASE WHEN final_status = 'cancelled' THEN 'council_run.cancelled'
           ELSE 'council_run.failed' END,
      jsonb_build_object('workspace_id', j.workspace_id,
                         'run_id', j.run_id, 'job_id', j.id),
      jsonb_build_object('status', final_status,
                         'error_code', CASE WHEN final_status = 'failed'
                           THEN COALESCE(p_error_code, 'worker_error') ELSE NULL END)
    );
  END IF;
  RETURN final_status;
END;
$$;

CREATE OR REPLACE FUNCTION app.worker_complete_council_run(
  p_job_id uuid, p_worker_id uuid, p_outcome varchar, p_result jsonb
)
RETURNS varchar
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, app
SET row_security = off
AS $$
DECLARE j public.worker_jobs%ROWTYPE;
DECLARE event_sequence bigint;
BEGIN
  IF p_outcome IS NULL OR p_outcome NOT IN (
    'consensus','qualified_consensus','unresolved_disagreement','insufficient_evidence'
  ) OR p_result IS NULL OR jsonb_typeof(p_result) <> 'object' THEN
    RAISE EXCEPTION 'invalid Council run result' USING ERRCODE = '22023';
  END IF;

  SELECT * INTO j FROM public.worker_jobs
  WHERE id = p_job_id AND job_type = 'council.run'
    AND run_id IS NOT NULL AND status = 'leased'
    AND lease_owner = p_worker_id AND lease_expires_at > now()
  FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'lease_lost';
  END IF;
  IF j.cancel_requested_at IS NOT NULL THEN
    RETURN 'cancel_requested';
  END IF;

  UPDATE public.council_runs
  SET status = 'completed', outcome = p_outcome, result = p_result, updated_at = now()
  WHERE id = j.run_id AND workspace_id = j.workspace_id AND status = 'running';
  IF NOT FOUND THEN
    RETURN 'run_not_running';
  END IF;

  UPDATE public.worker_jobs
  SET status = 'completed', lease_owner = NULL, lease_expires_at = NULL,
      heartbeat_at = NULL, updated_at = now()
  WHERE id = j.id;

  UPDATE public.workspace_event_counters
  SET last_sequence = last_sequence + 1
  WHERE workspace_id = j.workspace_id
  RETURNING last_sequence INTO event_sequence;
  IF event_sequence IS NULL THEN
    RAISE EXCEPTION 'workspace event counter is missing';
  END IF;
  INSERT INTO public.workspace_events
    (workspace_id, sequence, event_type, resource, payload)
  VALUES (
    j.workspace_id, event_sequence, 'council_run.completed',
    jsonb_build_object('workspace_id', j.workspace_id,
                       'run_id', j.run_id, 'job_id', j.id),
    jsonb_build_object('status', 'completed', 'outcome', p_outcome)
  );
  RETURN 'completed';
END;
$$;

REVOKE ALL ON FUNCTION app.worker_complete_council_run(uuid, uuid, varchar, jsonb) FROM PUBLIC;
COMMIT;
