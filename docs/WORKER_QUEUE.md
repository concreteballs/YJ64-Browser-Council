# Durable worker queue

**Status:** database-backed queue plus Council run transition/finalization functions; not yet a production worker service.

## Job contract

`worker_jobs` stores tenant-owned jobs with a stable ID, optional Council run ID, typed job name, JSON metadata payload, availability time, bounded attempts, lease owner/expiry, heartbeat and cancellation-request timestamp. Payloads must contain identifiers and non-secret metadata only. Provider credentials and browser profile material are resolved through separate protected services.

Allowed states:
- `queued`: eligible when `available_at <= now()`.
- `leased`: exclusively owned until lease expiry; heartbeats extend the lease.
- `completed`, `failed`, `cancelled`: terminal.

## Concurrency and recovery

`app.worker_claim_job` claims one eligible job with `FOR UPDATE SKIP LOCKED`. A concurrent worker skips rows already locked by another claimant. Expired leases can be reclaimed, incrementing `attempts`. Expired leases at the attempt limit are marked failed. If cancellation was requested before a worker disappeared, lease recovery finalizes the job as `cancelled` instead of retrying it or leaving it leased indefinitely. A worker may heartbeat or finish only while it owns a live lease. A stale worker receives `lease_lost` and cannot overwrite the new owner's state.

Failures are re-queued with bounded delay while attempts remain; the final failure is terminal. The queue does not automatically retry uncertain external side effects: provider adapters must classify/reconcile those operations before deciding whether a job is safe to retry.

## Privilege boundary

The worker role receives `EXECUTE` only on four narrowly scoped `SECURITY DEFINER` functions: claim, heartbeat, generic finish and Council-run completion. It receives no direct table privileges. Functions use a fixed `search_path`, disable row security for their owner-controlled operation, validate lease durations and check lease ownership. Production provisioning must grant these function privileges to a dedicated worker database identity, never to the public API runtime identity.

Tenant users see queue rows only through workspace RLS. The database migration does not create production roles or credentials; deployment provisioning remains explicit.

## Current limitations

- This is the durable queue persistence/client layer, not a running polling worker or deployed worker service.
- Council run claim transitions, terminal failure/cancellation synchronization and outcome-gated completion are now implemented in migration `0003_council_run_lifecycle.sql`. The API can enqueue, inspect and cancel runs. A continuously running worker remains open.
- No model/provider calls are made by this queue layer.
- The PostgreSQL smoke test verifies least privilege, claim, heartbeat, retry, lease expiry, cancellation acknowledgement, Council run start and outcome-gated completion. The API tests cover the enqueue contract.
- Readiness remains `503` until a real worker service is deployed and verified.

## Cancellation API

`POST /api/v1/jobs/{job_id}/cancel` is workspace-scoped. A queued job is cancelled immediately; a leased job receives a durable `cancel_requested_at` marker and remains leased until its worker acknowledges the request. Repeated requests are idempotent and do not emit duplicate request events. Terminal jobs remain unchanged. The worker heartbeat returns `false` after cancellation is requested; the worker must stop its operation and call finish, which records `cancelled` rather than success. The API writes `worker_job.cancelled` or `worker_job.cancel_requested` to the workspace event log in the same transaction as the state change.
\n\n## Council run lifecycle\n\nA `council.run` job moves its linked run from `queued` to `running` when claimed. Final worker failure/cancellation is reflected in the run and emits a workspace event. A Council run cannot be completed through generic `worker_finish_job(..., succeeded=true)`; the worker must call `app.worker_complete_council_run` with one of the four allowed analytical outcomes and a JSON object result. That function atomically persists the result and outcome, completes the job, and emits `council_run.completed`. The API status endpoint returns the stored result. No result or consensus is fabricated by the queue.\n\n\nCompletion validation requires a result object with matching `run_id`, `status=completed`, matching outcome, a non-empty summary and the required participant-position, dissent, claim, evidence-reference, assumption and limitation arrays. `consensus` and `qualified_consensus` are rejected when participant positions or explicit claims are empty. This is a database-level minimum guard; full semantic/evidence validation remains the responsibility of the Council engine and contract validator.\n