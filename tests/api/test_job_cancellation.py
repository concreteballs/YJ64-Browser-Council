import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.auth import Principal, get_current_principal
from apps.api.main import app
from apps.api.routes.workspaces import get_database


JOB_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WORKSPACE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
PRINCIPAL_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


class FakeConnection:
    def __init__(self, status):
        self.status = status
        self.cancel_requested = None
        self.event_sequence = 0
        self.executed = []

    async def fetchrow(self, query, *args):
        self.executed.append((query, args))
        if "SELECT id, workspace_id, run_id, status, cancel_requested_at" in query:
            return {
                "id": JOB_ID,
                "workspace_id": WORKSPACE_ID,
                "run_id": None,
                "status": self.status,
                "cancel_requested_at": self.cancel_requested,
            }
        if "UPDATE worker_jobs" in query:
            if "status = 'cancelled'" in query:
                self.status = "cancelled"
            elif "cancel_requested_at = now()" in query:
                self.cancel_requested = datetime.now(timezone.utc)
            return {"id": JOB_ID}
        if "UPDATE workspace_event_counters" in query:
            self.event_sequence += 1
            return {"last_sequence": self.event_sequence}
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "INSERT 0 1"


class FakeDatabase:
    def __init__(self, status):
        self.connection = FakeConnection(status)

    @asynccontextmanager
    async def tenant_transaction(self, principal_id):
        yield self.connection


class JobCancellationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.principal = Principal(PRINCIPAL_ID, "https://issuer.example", "user-123")
        self.database = FakeDatabase("queued")
        app.dependency_overrides[get_current_principal] = lambda: self.principal
        app.dependency_overrides[get_database] = lambda: self.database

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_queued_job_is_cancelled_immediately(self):
        response = self.client.post(f"/api/v1/jobs/{JOB_ID}/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertFalse(response.json()["cancellation_requested"])
        self.assertTrue(any("worker_job.cancelled" in str(args) for _, args in self.database.connection.executed))

    def test_leased_job_receives_cancellation_request(self):
        self.database.connection.status = "leased"
        response = self.client.post(f"/api/v1/jobs/{JOB_ID}/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "leased")
        self.assertTrue(response.json()["cancellation_requested"])
        self.assertIsNotNone(self.database.connection.cancel_requested)

    def test_terminal_job_is_not_changed(self):
        self.database.connection.status = "completed"
        response = self.client.post(f"/api/v1/jobs/{JOB_ID}/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertFalse(response.json()["cancellation_requested"])
        self.assertFalse(any("workspace_event_counters" in query for query, _ in self.database.connection.executed))


if __name__ == "__main__":
    unittest.main()
