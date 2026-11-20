import unittest
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.auth import Principal, get_current_principal
from apps.api.main import app
from apps.api.routes.workspaces import get_database


WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
RUN_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
JOB_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
PRINCIPAL_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


class FakeConnection:
    def __init__(self, job_status="queued", run_status="queued"):
        self.job_status = job_status
        self.run_status = run_status
        self.cancel_requested = None
        self.calls = []

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        if "SELECT id, workspace_id, status" in query and "FROM council_runs" in query:
            return {"id": RUN_ID, "workspace_id": WORKSPACE_ID, "status": self.run_status}
        if "SELECT id, status, cancel_requested_at" in query and "FROM worker_jobs" in query:
            return {"id": JOB_ID, "status": self.job_status,
                    "cancel_requested_at": self.cancel_requested}
        if "UPDATE workspace_event_counters" in query:
            return {"last_sequence": 11}
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def execute(self, query, *args):
        self.calls.append((query, args))
        if "SET status = 'cancelled'" in query and "worker_jobs" in query:
            self.job_status = "cancelled"
        if "SET cancel_requested_at = now()" in query:
            self.cancel_requested = True
        if "SET status = 'cancelled'" in query and "council_runs" in query:
            self.run_status = "cancelled"
        return "UPDATE 1"


class FakeDatabase:
    def __init__(self, job_status="queued", run_status="queued"):
        self.connection = FakeConnection(job_status, run_status)

    @asynccontextmanager
    async def tenant_transaction(self, principal_id):
        yield self.connection


class CouncilRunCancellationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.database = FakeDatabase()
        self.principal = Principal(PRINCIPAL_ID, "https://issuer.example", "user-123")
        app.dependency_overrides[get_current_principal] = lambda: self.principal
        app.dependency_overrides[get_database] = lambda: self.database

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_queued_run_is_cancelled_atomically(self):
        response = self.client.post(f"/api/v1/runs/{RUN_ID}/cancel")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertFalse(response.json()["cancellation_requested"])
        self.assertEqual(self.database.connection.job_status, "cancelled")
        self.assertTrue(any(
            "council_run.cancelled" in str(args)
            for query, args in self.database.connection.calls
            if "INSERT INTO workspace_events" in query
        ))

    def test_leased_run_records_request_without_claiming_it_stopped(self):
        self.database = FakeDatabase(job_status="leased", run_status="running")
        app.dependency_overrides[get_database] = lambda: self.database
        response = self.client.post(f"/api/v1/runs/{RUN_ID}/cancel")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "running")
        self.assertTrue(response.json()["cancellation_requested"])
        self.assertTrue(self.database.connection.cancel_requested)
        self.assertTrue(any(
            "council_run.cancel_requested" in str(args)
            for query, args in self.database.connection.calls
            if "INSERT INTO workspace_events" in query
        ))


if __name__ == "__main__":
    unittest.main()
