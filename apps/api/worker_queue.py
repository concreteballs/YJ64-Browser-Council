import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from apps.api.database import Database


@dataclass(frozen=True)
class ClaimedJob:
    id: UUID
    workspace_id: UUID
    run_id: UUID | None
    job_type: str
    payload: dict[str, Any]
    attempts: int
    lease_expires_at: datetime


class WorkerQueue:
    """Least-privilege client for the database-owned durable queue functions."""

    def __init__(self, database: Database):
        self.database = database

    async def claim(self, worker_id: UUID, lease_seconds: int = 60) -> ClaimedJob | None:
        if self.database.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM app.worker_claim_job($1, $2)",
                worker_id,
                lease_seconds,
            )
        return ClaimedJob(**dict(row)) if row else None

    async def heartbeat(
        self, job_id: UUID, worker_id: UUID, lease_seconds: int = 60
    ) -> bool:
        if self.database.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.database.pool.acquire() as connection:
            return await connection.fetchval(
                "SELECT app.worker_heartbeat_job($1, $2, $3)",
                job_id,
                worker_id,
                lease_seconds,
            )

    async def finish(
        self,
        job_id: UUID,
        worker_id: UUID,
        *,
        succeeded: bool,
        error_code: str | None = None,
        retry_delay_seconds: int = 30,
    ) -> str:
        if self.database.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.database.pool.acquire() as connection:
            return await connection.fetchval(
                "SELECT app.worker_finish_job($1, $2, $3, $4, $5)",
                job_id,
                worker_id,
                succeeded,
                error_code,
                retry_delay_seconds,
            )

    async def complete_council_run(
        self,
        job_id: UUID,
        worker_id: UUID,
        *,
        outcome: str,
        result: dict[str, Any],
    ) -> str:
        """Atomically persist a Council result/outcome and complete its leased job."""
        if self.database.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.database.pool.acquire() as connection:
            return await connection.fetchval(
                "SELECT app.worker_complete_council_run($1, $2, $3, $4::jsonb)",
                job_id,
                worker_id,
                outcome,
                json.dumps(result),
            )
