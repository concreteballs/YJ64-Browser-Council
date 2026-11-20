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
CONNECTION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CONVERSATION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
PRINCIPAL_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.idempotency = None
        self.last_sequence = 0
        self.now = datetime.now(timezone.utc)

    async def fetch(self, query, *args):
        self.executed.append((query, args))
        return []

    async def fetchrow(self, query, *args):
        self.executed.append((query, args))
        if "SELECT id FROM provider_connections" in query:
            return {"id": CONNECTION_ID}
        if "INSERT INTO provider_connections" in query:
            return {
                "id": CONNECTION_ID, "name": args[1], "provider": args[2],
                "connection_type": args[3], "status": "unconfigured", "created_at": self.now,
            }
        if "INSERT INTO conversations" in query:
            return {
                "id": CONVERSATION_ID, "workspace_id": args[0], "title": args[1],
                "provider_connection_id": args[2], "created_at": self.now, "updated_at": self.now,
            }
        if "SELECT workspace_id FROM conversations" in query:
            return {"workspace_id": WORKSPACE_ID}
        if "INSERT INTO idempotency_records" in query:
            if self.idempotency is not None:
                return None
            self.idempotency = {"request_hash": args[3], "response_body": None}
            return {"id": UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")}
        if "SELECT request_hash, response_body" in query:
            return self.idempotency
        if "UPDATE conversation_counters" in query:
            self.last_sequence += 1
            return {"last_sequence": self.last_sequence}
        if "INSERT INTO messages" in query:
            return {
                "id": UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
                "client_message_id": args[2], "conversation_id": args[1],
                "role": "user", "content": args[3], "status": "completed",
                "sequence": args[4], "created_at": self.now,
            }
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def execute(self, query, *args):
        self.executed.append((query, args))
        if "UPDATE idempotency_records" in query:
            self.idempotency["response_body"] = args[0]
        return "INSERT 0 1"


class FakeDatabase:
    def __init__(self):
        self.connection = FakeConnection()

    @asynccontextmanager
    async def tenant_transaction(self, principal_id):
        self.principal_id = principal_id
        yield self.connection


class ConversationRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.principal = Principal(PRINCIPAL_ID, "https://issuer.example", "user-123")
        self.database = FakeDatabase()
        app.dependency_overrides[get_current_principal] = lambda: self.principal
        app.dependency_overrides[get_database] = lambda: self.database

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_create_provider_connection_stores_only_metadata(self):
        response = self.client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/provider-connections",
            json={"name": "OpenAI API", "provider": "openai", "connection_type": "api"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "unconfigured")
        sql = " ".join(query for query, _ in self.database.connection.executed)
        self.assertNotIn("secret_reference", sql)

    def test_create_conversation_creates_order_counter(self):
        response = self.client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/conversations",
            json={
                "title": "First chat",
                "provider_connection_id": str(CONNECTION_ID),
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], str(CONVERSATION_ID))
        self.assertTrue(any("conversation_counters" in query for query, _ in self.database.connection.executed))

    def test_message_create_is_idempotent(self):
        payload = {
            "client_message_id": "client-msg-1",
            "content": "Check this hypothesis",
            "idempotency_key": "idempotency-0001",
        }
        path = f"/api/v1/conversations/{CONVERSATION_ID}/messages"
        headers = {"Idempotency-Key": payload["idempotency_key"]}
        first = self.client.post(path, json=payload, headers=headers)
        second = self.client.post(path, json=payload, headers=headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        message_inserts = sum("INSERT INTO messages" in query for query, _ in self.database.connection.executed)
        self.assertEqual(message_inserts, 1)

    def test_idempotency_header_must_match_body(self):
        response = self.client.post(
            f"/api/v1/conversations/{CONVERSATION_ID}/messages",
            json={
                "client_message_id": "client-msg-2",
                "content": "Message",
                "idempotency_key": "body-key-0001",
            },
            headers={"Idempotency-Key": "different-key-0002"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
