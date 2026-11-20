import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.auth import Principal, get_current_principal
from apps.api.database import Database
from apps.api.main import app
from apps.api.routes.workspaces import get_database


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.fetchrow_result = {
            "id": UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            "name": "Research",
            "description": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    async def fetch(self, query, *args):
        return []

    async def fetchrow(self, query, *args):
        self.executed.append((query, args))
        return self.fetchrow_result

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "INSERT 0 1"


class FakeDatabase:
    def __init__(self):
        self.connection = FakeConnection()

    @asynccontextmanager
    async def tenant_transaction(self, principal_id):
        self.principal_id = principal_id
        yield self.connection


class WorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.principal = Principal(
            user_id=UUID("11111111-1111-4111-8111-111111111111"),
            issuer="https://issuer.example",
            subject="user-123",
        )
        self.database = FakeDatabase()
        app.dependency_overrides[get_current_principal] = lambda: self.principal
        app.dependency_overrides[get_database] = lambda: self.database

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_create_workspace_creates_owner_membership_and_event_counter(self):
        response = self.client.post("/api/v1/workspaces", json={"name": "  Research  "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Research")
        self.assertEqual(self.database.principal_id, self.principal.user_id)
        self.assertEqual(len(self.database.connection.executed), 3)

    def test_list_workspaces_uses_tenant_transaction(self):
        response = self.client.get("/api/v1/workspaces")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertEqual(self.database.principal_id, self.principal.user_id)

    def test_blank_workspace_name_is_rejected(self):
        response = self.client.post("/api/v1/workspaces", json={"name": "   "})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
