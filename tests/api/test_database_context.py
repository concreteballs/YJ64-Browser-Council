import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from apps.api.database import Database


class AsyncContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class DatabaseContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_tenant_identity_is_set_transaction_locally(self):
        database = Database(None)
        connection = MagicMock()
        connection.execute = AsyncMock()
        connection.transaction.return_value = AsyncContext()
        database.pool = MagicMock()
        database.pool.acquire = AsyncMock(return_value=connection)
        database.pool.release = AsyncMock()

        principal = UUID("11111111-1111-4111-8111-111111111111")
        async with database.tenant_transaction(principal):
            pass

        connection.execute.assert_awaited_once_with(
            "SELECT set_config('app.user_id', $1, true)",
            str(principal),
        )
        database.pool.release.assert_awaited_once_with(connection)

    async def test_tenant_transaction_rejects_missing_pool(self):
        database = Database(None)
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            async with database.tenant_transaction(UUID(int=1)):
                pass


if __name__ == "__main__":
    unittest.main()
