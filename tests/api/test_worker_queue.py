import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from apps.api.worker_queue import WorkerQueue


WORKER_ID = UUID("11111111-1111-4111-8111-111111111111")
JOB_ID = UUID("22222222-2222-4222-8222-222222222222")
WORKSPACE_ID = UUID("33333333-3333-4333-8333-333333333333")


class FakeConnection:
    def __init__(self):
        self.calls = []

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return {
            "id": JOB_ID,
            "workspace_id": WORKSPACE_ID,
            "run_id": None,
            "job_type": "test.noop",
            "payload": {"safe": True},
            "attempts": 1,
            "lease_expires_at": datetime.now(timezone.utc),
        }

    async def fetchval(self, query, *args):
        self.calls.append((query, args))
        if "heartbeat" in query:
            return True
        if "finish" in query:
            return "completed"
        return None


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


class FakeDatabase:
    def __init__(self, connected=True):
        self.pool = FakePool() if connected else None


class WorkerQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_claim_returns_typed_job(self):
        queue = WorkerQueue(FakeDatabase())
        job = await queue.claim(WORKER_ID, 90)
        self.assertEqual(job.id, JOB_ID)
        self.assertEqual(job.workspace_id, WORKSPACE_ID)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.payload, {"safe": True})

    async def test_heartbeat_and_finish_use_database_functions(self):
        queue = WorkerQueue(FakeDatabase())
        self.assertTrue(await queue.heartbeat(JOB_ID, WORKER_ID))
        self.assertEqual(
            await queue.finish(JOB_ID, WORKER_ID, succeeded=True),
            "completed",
        )

    async def test_unconfigured_database_fails_closed(self):
        queue = WorkerQueue(FakeDatabase(connected=False))
        with self.assertRaises(RuntimeError):
            await queue.claim(WORKER_ID)


if __name__ == "__main__":
    unittest.main()
