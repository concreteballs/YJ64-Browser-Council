import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.auth import Principal, get_current_principal
from apps.api.main import app
from apps.api.routes.workspaces import get_database


WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PRINCIPAL_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
EVENT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


class FakeConnection:
    def __init__(self):
        self.calls = []

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        if "SELECT id FROM workspaces" in query:
            return {"id": WORKSPACE_ID}
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return [{
            "id": EVENT_ID,
            "sequence": 3,
            "event_type": "message.created",
            "resource": {"workspace_id": str(WORKSPACE_ID)},
            "payload": {"message_id": "message-1"},
            "occurred_at": datetime.now(timezone.utc),
        }]


class FakeDatabase:
    def __init__(self):
        self.connection = FakeConnection()

    @asynccontextmanager
    async def tenant_transaction(self, principal_id):
        yield self.connection


class WorkspaceEventTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.principal = Principal(PRINCIPAL_ID, "https://issuer.example", "user-123")
        self.database = FakeDatabase()
        app.dependency_overrides[get_current_principal] = lambda: self.principal
        app.dependency_overrides[get_database] = lambda: self.database

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_event_replay_uses_sequence_cursor(self):
        response = self.client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/events?after_sequence=2&limit=20"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["sequence"], 3)
        query, args = self.database.connection.calls[-1]
        self.assertIn("sequence > $2", query)
        self.assertEqual(args, (WORKSPACE_ID, 2, 20))

    def test_event_stream_rejects_invalid_cursor(self):
        response = self.client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/events/stream",
            headers={"Last-Event-ID": "not-a-number"},
        )
        self.assertEqual(response.status_code, 422)

    def test_event_replay_rejects_invalid_limit(self):
        response = self.client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/events?limit=501"
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
