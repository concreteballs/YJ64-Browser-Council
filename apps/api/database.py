from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

import asyncpg


class Database:
    """Small asyncpg pool wrapper with transaction-scoped tenant identity."""

    def __init__(self, dsn: str | None):
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    @property
    def connected(self) -> bool:
        return self.pool is not None

    async def connect(self) -> None:
        if not self.dsn:
            return
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def ping(self) -> bool:
        if self.pool is None:
            return False
        async with self.pool.acquire() as connection:
            return await connection.fetchval("SELECT 1") == 1

    @asynccontextmanager
    async def tenant_transaction(self, principal_id: UUID) -> AsyncIterator[asyncpg.Connection]:
        if self.pool is None:
            raise RuntimeError("Database pool is not connected")
        connection = await self.pool.acquire()
        try:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.user_id', $1, true)",
                    str(principal_id),
                )
                yield connection
        finally:
            await self.pool.release(connection)
