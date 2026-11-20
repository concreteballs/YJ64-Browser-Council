import json
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.auth import Principal, get_current_principal
from apps.api.main import app
from apps.api.routes.workspaces import get_database


WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
COUNCIL_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
RUN_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
JOB_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
PRINCIPAL_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
NOW = datetime.now(timezone.utc)


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.idempotency_inserted = True
        self.participant_count = 2
        self.ready_count = 2

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        if "SELECT id, workspace_id FROM councils" in query:
            return {"id": COUNCIL_ID, "workspace_id": WORKSPACE_ID}
        if "count(*) FILTER (WHERE p.enabled) AS total" in query:
            return {"total": self.participant_count, "ready": self.ready_count}
        if "INSERT INTO idempotency_records" in query:
            return {"id": UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")} if self.idempotency_inserted else None
        if "INSERT INTO council_runs" in query:
            return {
                "id": RUN_ID, "workspace_id": WORKSPACE_ID, "council_id": COUNCIL_ID,
                "status": "queued", "outcome": None, "created_at": NOW, "updated_at": NOW,
            }
        if "INSERT INTO worker_jobs" in query:
            return {"id": JOB_ID}
        if "UPDATE workspace_event_counters" in query:
            return {"last_sequence": 7}
        if "SELECT request_hash, response_body FROM idempotency_records" in query:
            return None
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return "UPDATE 1"


class FakeDatabase:
    def __init__(self):
        self.connection = FakeConnection()

    @asynccontextmanager
    async def tenant_transaction(self, principal_id):
        yield self.connection


class CouncilRunApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.database = FakeDatabase()
        self.principal = Principal(PRINCIPAL_ID, "https://issuer.example", "user-123")
        app.dependency_overrides[get_current_principal] = lambda: self.principal
        app.dependency_overrides[get_database] = lambda: self.database

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_run_creation_atomically_enqueues_identifier_only_job(self):
        response = self.client.post(
            f"/api/v1/councils/{COUNCIL_ID}/runs",
            headers={"Idempotency-Key": "council-run-test-001"},
            json={"prompt": "Compare the competing engineering hypotheses."},
        )
        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["id"], str(RUN_ID))
        self.assertEqual(body["job_id"], str(JOB_ID))
        self.assertEqual(body["status"], "queued")

        job_call = next(
            args for query, args in self.database.connection.calls
            if "INSERT INTO worker_jobs" in query
        )
        job_query = next(
            query for query, args in self.database.connection.calls
            if "INSERT INTO worker_jobs" in query
        )
        self.assertIn("'council.run'", job_query)
        payload = json.loads(job_call[2])
        self.assertEqual(payload, {"run_id": str(RUN_ID)})
        self.assertNotIn("prompt", payload)

        statements = [query for query, _ in self.database.connection.calls]
        self.assertTrue(any("INSERT INTO council_runs" in query for query in statements))
        self.assertTrue(any("INSERT INTO workspace_events" in query for query in statements))
        self.assertTrue(any("UPDATE idempotency_records" in query for query in statements))

    def test_run_creation_requires_active_participant(self):
        self.database.connection.ready_count = 0
        response = self.client.post(
            f"/api/v1/councils/{COUNCIL_ID}/runs",
            headers={"Idempotency-Key": "council-run-test-002"},
            json={"prompt": "Test prompt"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(any(
            "INSERT INTO council_runs" in query
            for query, _ in self.database.connection.calls
        ))


if __name__ == "__main__":
    unittest.main()
