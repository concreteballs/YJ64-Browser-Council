-- Run after both migrations as the database owner.
DO $$
DECLARE ws uuid := gen_random_uuid();
DECLARE job uuid := gen_random_uuid();
BEGIN
  INSERT INTO workspaces(id, name, created_by) VALUES
    (ws, 'worker queue smoke', gen_random_uuid());
  INSERT INTO workspace_members(workspace_id, user_id, role)
    SELECT ws, created_by, 'owner' FROM workspaces WHERE id = ws;
  INSERT INTO workspace_event_counters(workspace_id, last_sequence)
    VALUES (ws, 0);
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
    VALUES (retry_job, ws, 'test.retry', 2);
  INSERT INTO worker_jobs(id, workspace_id, job_type, max_attempts, available_at)
    VALUES (expiry_job, ws, 'test.expiry', 2, now() + interval '1 hour');
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
UPDATE worker_jobs SET available_at = now() - interval '1 second'
WHERE id = current_setting('test.expiry_job_id')::uuid;
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

-- A running worker acknowledges a cancellation request as a cancelled terminal job.
DO $$
DECLARE ws uuid := current_setting('test.worker_workspace_id')::uuid;
DECLARE job uuid := gen_random_uuid();
BEGIN
  INSERT INTO worker_jobs(id, workspace_id, job_type, max_attempts)
    VALUES (job, ws, 'test.cancel', 2);
  PERFORM set_config('test.cancel_job_id', job::text, false);
END $$;

SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.cancel_job_id')::uuid;
DECLARE worker_id uuid := gen_random_uuid();
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(worker_id, 60);
  IF claimed.id IS DISTINCT FROM job_id THEN
    RAISE EXCEPTION 'cancellation job was not claimed';
  END IF;
  PERFORM set_config('test.cancel_worker_id', worker_id::text, false);
END $$;
RESET ROLE;

UPDATE worker_jobs SET cancel_requested_at = now()
WHERE id = current_setting('test.cancel_job_id')::uuid;

SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.cancel_job_id')::uuid;
DECLARE worker_id uuid := current_setting('test.cancel_worker_id')::uuid;
BEGIN
  IF app.worker_heartbeat_job(job_id, worker_id, 60) THEN
    RAISE EXCEPTION 'heartbeat continued after cancellation request';
  END IF;
  IF app.worker_finish_job(job_id, worker_id, true, NULL, 30) <> 'cancelled' THEN
    RAISE EXCEPTION 'worker did not acknowledge cancellation';
  END IF;
END $$;
RESET ROLE;

-- If a worker crashes after cancellation is requested, lease recovery finalizes
-- cancellation instead of leaving a permanently leased row or retrying the work.
DO $$
DECLARE ws uuid := current_setting('test.worker_workspace_id')::uuid;
DECLARE job uuid := gen_random_uuid();
BEGIN
  INSERT INTO worker_jobs(id, workspace_id, job_type, max_attempts)
    VALUES (job, ws, 'test.cancel_crash', 2);
  PERFORM set_config('test.cancel_crash_job_id', job::text, false);
END $$;

SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.cancel_crash_job_id')::uuid;
DECLARE worker_id uuid := gen_random_uuid();
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(worker_id, 60);
  IF claimed.id IS DISTINCT FROM job_id THEN
    RAISE EXCEPTION 'cancel-crash job was not claimed';
  END IF;
END $$;
RESET ROLE;

UPDATE worker_jobs
SET cancel_requested_at = now(), lease_expires_at = now() - interval '1 second'
WHERE id = current_setting('test.cancel_crash_job_id')::uuid;

SET ROLE browser_council_worker;
DO $$
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(gen_random_uuid(), 60);
  IF FOUND THEN
    RAISE EXCEPTION 'expired cancelled job was incorrectly re-claimed';
  END IF;
END $$;
RESET ROLE;

DO $$
BEGIN
  IF (SELECT status FROM worker_jobs
      WHERE id = current_setting('test.cancel_crash_job_id')::uuid) <> 'cancelled' THEN
    RAISE EXCEPTION 'expired cancellation request was not finalized';
  END IF;
END $$;


-- Council runs transition on claim and complete only with a persisted outcome/result.
DO $$
DECLARE ws uuid := current_setting('test.worker_workspace_id')::uuid;
DECLARE council uuid := gen_random_uuid();
DECLARE run uuid := gen_random_uuid();
DECLARE job uuid := gen_random_uuid();
DECLARE owner_id uuid;
BEGIN
  SELECT user_id INTO owner_id FROM workspace_members
  WHERE workspace_id = ws AND role = 'owner' LIMIT 1;
  INSERT INTO councils(id, workspace_id, name, created_by)
    VALUES (council, ws, 'Lifecycle smoke council', owner_id);
  INSERT INTO council_runs(id, workspace_id, council_id, prompt, created_by)
    VALUES (run, ws, council, 'Validate lifecycle state transitions', owner_id);
  INSERT INTO worker_jobs(id, workspace_id, run_id, job_type, payload)
    VALUES (job, ws, run, 'council.run', jsonb_build_object('run_id', run));
  PERFORM set_config('test.council_run_id', run::text, false);
  PERFORM set_config('test.council_job_id', job::text, false);
END $$;

SET ROLE browser_council_worker;
DO $$
DECLARE job_id uuid := current_setting('test.council_job_id')::uuid;
DECLARE worker_id uuid := gen_random_uuid();
DECLARE claimed record;
BEGIN
  SELECT * INTO claimed FROM app.worker_claim_job(worker_id, 60);
  IF claimed.id IS DISTINCT FROM job_id OR claimed.job_type <> 'council.run' THEN
    RAISE EXCEPTION 'Council run job was not claimed';
  END IF;
  PERFORM set_config('test.council_worker_id', worker_id::text, false);
  IF app.worker_finish_job(job_id, worker_id, true, NULL, 30) <> 'completion_required' THEN
    RAISE EXCEPTION 'generic completion bypassed Council result finalization';
  END IF;
  BEGIN
    PERFORM app.worker_complete_council_run(
      job_id, worker_id, 'consensus',
      jsonb_build_object(
        'run_id', current_setting('test.council_run_id'),
        'status', 'completed', 'outcome', 'consensus',
        'summary', 'unsupported consensus',
        'participant_positions', '[]'::jsonb, 'dissent', '[]'::jsonb,
        'claims', '[]'::jsonb, 'evidence_refs', '[]'::jsonb,
        'assumptions', '[]'::jsonb, 'limitations', '[]'::jsonb
      )
    );
    RAISE EXCEPTION 'unsupported consensus result was accepted';
  EXCEPTION WHEN invalid_parameter_value THEN
    NULL;
  END;
  IF app.worker_complete_council_run(
    job_id, worker_id, 'insufficient_evidence',
    jsonb_build_object(
      'run_id', current_setting('test.council_run_id'),
      'status', 'completed',
      'outcome', 'insufficient_evidence',
      'summary', 'smoke result',
      'participant_positions', '[]'::jsonb,
      'dissent', '[]'::jsonb,
      'claims', '[]'::jsonb,
      'evidence_refs', '[]'::jsonb,
      'assumptions', '[]'::jsonb,
      'limitations', jsonb_build_array('test fixture')
    )
  ) <> 'completed' THEN
    RAISE EXCEPTION 'Council run did not complete with a validated outcome';
  END IF;
END $$;
RESET ROLE;

DO $$
DECLARE run_id uuid := current_setting('test.council_run_id')::uuid;
DECLARE job_id uuid := current_setting('test.council_job_id')::uuid;
BEGIN
  IF (SELECT status FROM council_runs WHERE id = run_id) <> 'completed' THEN
    RAISE EXCEPTION 'Council run status was not completed';
  END IF;
  IF (SELECT outcome FROM council_runs WHERE id = run_id) <> 'insufficient_evidence' THEN
    RAISE EXCEPTION 'Council run outcome was not persisted';
  END IF;
  IF (SELECT result->>'summary' FROM council_runs WHERE id = run_id) <> 'smoke result' THEN
    RAISE EXCEPTION 'Council run result was not persisted';
  END IF;
  IF (SELECT status FROM worker_jobs WHERE id = job_id) <> 'completed' THEN
    RAISE EXCEPTION 'Council run queue job was not completed';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM workspace_events
    WHERE workspace_id = current_setting('test.worker_workspace_id')::uuid
      AND event_type = 'council_run.started'
  ) OR NOT EXISTS (
    SELECT 1 FROM workspace_events
    WHERE workspace_id = current_setting('test.worker_workspace_id')::uuid
      AND event_type = 'council_run.completed'
  ) THEN
    RAISE EXCEPTION 'Council run lifecycle events are missing';
  END IF;
END $$;
