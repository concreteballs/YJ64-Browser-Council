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
  PERFORM set_config('test.worker_workspace_id', ws::text, false);
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
DECLARE ws uuid := current_setting('test.worker_workspace_id')::uuid;
DECLARE retry_job uuid := gen_random_uuid();
DECLARE expiry_job uuid := gen_random_uuid();
BEGIN
  IF (SELECT status FROM worker_jobs WHERE id = current_setting('test.worker_job_id')::uuid) <> 'completed' THEN
    RAISE EXCEPTION 'job did not persist completed state';
  END IF;
  INSERT INTO worker_jobs(id, workspace_id, job_type, max_attempts)
    VALUES (retry_job, ws, 'test.retry', 2), (expiry_job, ws, 'test.expiry', 2);
  PERFORM set_config('test.retry_job_id', retry_job::text, false);
  PERFORM set_config('test.expiry_job_id', expiry_job::text, false);
END $$;

SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.retry_job_id')::uuid;
DECLARE worker_id uuid := gen_random_uuid();
DECLARE result_status varchar;
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(worker_id, 60);
  IF claimed.id IS DISTINCT FROM job_id THEN
    RAISE EXCEPTION 'retry job was not claimed';
  END IF;
  result_status := app.worker_finish_job(job_id, worker_id, false, 'temporary_failure', 1);
  IF result_status <> 'queued' THEN
    RAISE EXCEPTION 'expected retry queue state, got %', result_status;
  END IF;
END $$;
RESET ROLE;

-- Make the delayed retry eligible, then prove the attempt limit is terminal.
UPDATE worker_jobs SET available_at = now() - interval '1 second'
WHERE id = current_setting('test.retry_job_id')::uuid;
SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.retry_job_id')::uuid;
DECLARE worker_id uuid := gen_random_uuid();
DECLARE result_status varchar;
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(worker_id, 60);
  IF claimed.id IS DISTINCT FROM job_id OR claimed.attempts <> 2 THEN
    RAISE EXCEPTION 'retry attempt was not incremented';
  END IF;
  result_status := app.worker_finish_job(job_id, worker_id, false, 'permanent_failure', 1);
  IF result_status <> 'failed' THEN
    RAISE EXCEPTION 'expected terminal failure, got %', result_status;
  END IF;
END $$;
RESET ROLE;

-- Expired leases are reclaimed by another worker and attempts are incremented.
SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.expiry_job_id')::uuid;
DECLARE first_worker uuid := gen_random_uuid();
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(first_worker, 60);
  IF claimed.id IS DISTINCT FROM job_id THEN
    RAISE EXCEPTION 'lease-expiry job was not initially claimed';
  END IF;
  PERFORM set_config('test.first_worker_id', first_worker::text, false);
END $$;
RESET ROLE;

UPDATE worker_jobs SET lease_expires_at = now() - interval '1 second'
WHERE id = current_setting('test.expiry_job_id')::uuid;

SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.expiry_job_id')::uuid;
DECLARE second_worker uuid := gen_random_uuid();
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(second_worker, 60);
  IF claimed.id IS DISTINCT FROM job_id OR claimed.attempts <> 2 THEN
    RAISE EXCEPTION 'expired lease was not recovered by the next worker';
  END IF;
  IF app.worker_finish_job(job_id, current_setting('test.first_worker_id')::uuid, true, NULL, 30) <> 'lease_lost' THEN
    RAISE EXCEPTION 'stale worker was allowed to finish a reclaimed lease';
  END IF;
  IF app.worker_finish_job(job_id, second_worker, true, NULL, 30) <> 'completed' THEN
    RAISE EXCEPTION 'new lease owner could not complete job';
  END IF;
END $$;
RESET ROLE;
