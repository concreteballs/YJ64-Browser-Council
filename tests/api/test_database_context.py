import unittest
from unittest.mock import AsyncMock
from uuid import UUID

from apps.api.database import Database


class DatabaseContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_tenant_identity_is_set_transaction_locally(self):
        database = Database(None)
        connection = AsyncMock()
        database.pool = AsyncMock()
        acquire_context = database.pool.acquire.return_value
        acquire_context.__aenter__.return_value = connection
        acquire_context.__aexit__.return_value = False
        transaction_context = connection.transaction.return_value
        transaction_context.__aenter__.return_value = None
        transaction_context.__aexit__.return_value = False

        principal = UUID("11111111-1111-4111-8111-111111111111")
        async with database.tenant_transaction(principal):
            pass

        connection.execute.assert_awaited_once_with(
            "SELECT set_config('app.user_id', $1, true)",
            str(principal),
        )

    async def test_tenant_transaction_rejects_missing_pool(self):
        database = Database(None)
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            async with database.tenant_transaction(UUID(int=1)):
                pass


if __name__ == "__main__":
    unittest.main()
