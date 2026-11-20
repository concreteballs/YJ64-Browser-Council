-- Run after both migrations as the database owner.
DO $$
DECLARE ws uuid := gen_random_uuid();
DECLARE job uuid := gen_random_uuid();
BEGIN
  INSERT INTO workspaces(id, name, created_by) VALUES
    (ws, 'worker queue smoke', gen_random_uuid());
  INSERT INTO workspace_members(workspace_id, user_id, role)
    SELECT ws, created_by, 'owner' FROM workspaces WHERE id = ws;
  INSERT INTO worker_jobs(id, workspace_id, job_type, payload, max_attempts)
    VALUES (job, ws, 'test.noop', '{"resource":"smoke"}'::jsonb, 2);
  PERFORM set_config('test.worker_job_id', job::text, false);
END $$;

SET ROLE browser_council_worker;
DO $$
DECLARE claimed record;
DECLARE job_id uuid := current_setting('test.worker_job_id')::uuid;
DECLARE worker_id uuid := gen_random_uuid();
DECLARE result_status varchar;
BEGIN
  BEGIN
    PERFORM 1 FROM public.worker_jobs;
    RAISE EXCEPTION 'worker unexpectedly has direct table access';
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;

  SELECT * INTO claimed FROM app.worker_claim_job(worker_id, 60);
  IF claimed.id IS DISTINCT FROM job_id OR claimed.attempts <> 1 THEN
    RAISE EXCEPTION 'job claim did not return expected job';
  END IF;
  IF NOT app.worker_heartbeat_job(job_id, worker_id, 60) THEN
    RAISE EXCEPTION 'valid lease heartbeat was rejected';
  END IF;
  result_status := app.worker_finish_job(job_id, worker_id, true, NULL, 30);
  IF result_status <> 'completed' THEN
    RAISE EXCEPTION 'expected completed, got %', result_status;
  END IF;
  IF app.worker_heartbeat_job(job_id, worker_id, 60) THEN
    RAISE EXCEPTION 'terminal job accepted heartbeat';
  END IF;
END $$;
RESET ROLE;

DO $$
DECLARE ws uuid := current_setting('test.worker_job_id')::uuid;
BEGIN
  IF (SELECT status FROM worker_jobs WHERE id = ws) <> 'completed' THEN
    RAISE EXCEPTION 'job did not persist completed state';
  END IF;
END $$;
