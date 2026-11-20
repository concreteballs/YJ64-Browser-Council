import hashlib
import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from apps.api.auth import Principal, get_current_principal
from apps.api.database import Database
from apps.api.routes.workspaces import get_database


workspace_council_router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/councils", tags=["councils"]
)
council_router = APIRouter(prefix="/api/v1/councils", tags=["councils"])
run_router = APIRouter(prefix="/api/v1/runs", tags=["council-runs"])


class CouncilCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Council name cannot be blank")
        return value


class CouncilRead(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str
    created_at: datetime


class ParticipantCreate(BaseModel):
    provider_connection_id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    model_identifier: str | None = Field(default=None, max_length=160)
    position: int = Field(ge=0, le=1000)
    enabled: bool = True

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Participant display name cannot be blank")
        return value


class ParticipantRead(BaseModel):
    id: UUID
    council_id: UUID
    provider_connection_id: UUID
    display_name: str
    model_identifier: str | None
    position: int
    enabled: bool


class RunCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=50000)

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prompt cannot be blank")
        return value


class RunRead(BaseModel):
    id: UUID
    workspace_id: UUID
    council_id: UUID
    status: str
    outcome: str | None
    created_at: datetime
    updated_at: datetime
    job_id: UUID | None = None
    result: dict | None = None


async def _append_event(connection, workspace_id: UUID, event_type: str,
                        resource: dict, payload: dict) -> None:
    counter = await connection.fetchrow(
        """
        UPDATE workspace_event_counters
        SET last_sequence = last_sequence + 1
        WHERE workspace_id = $1
        RETURNING last_sequence
        """,
        workspace_id,
    )
    if counter is None:
        raise HTTPException(status_code=409, detail="Workspace event counter is missing")
    await connection.execute(
        """
        INSERT INTO workspace_events (workspace_id, sequence, event_type, resource, payload)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
        """,
        workspace_id, counter["last_sequence"], event_type,
        json.dumps(resource), json.dumps(payload),
    )


@workspace_council_router.get("", response_model=list[CouncilRead])
async def list_councils(
    workspace_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        rows = await connection.fetch(
            """
            SELECT id, workspace_id, name, description, created_at
            FROM councils WHERE workspace_id = $1
            ORDER BY created_at, id
            """,
            workspace_id,
        )
    return [CouncilRead(**dict(row)) for row in rows]


@workspace_council_router.post("", response_model=CouncilRead,
                               status_code=status.HTTP_201_CREATED)
async def create_council(
    workspace_id: UUID,
    payload: CouncilCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO councils (workspace_id, name, description, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id, workspace_id, name, description, created_at
            """,
            workspace_id, payload.name, payload.description, principal.user_id,
        )
        await _append_event(
            connection, workspace_id, "council.created",
            {"workspace_id": str(workspace_id), "council_id": str(row["id"])},
            {"name": row["name"]},
        )
    return CouncilRead(**dict(row))


@council_router.get("/{council_id}/participants", response_model=list[ParticipantRead])
async def list_participants(
    council_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        rows = await connection.fetch(
            """
            SELECT p.id, p.council_id, p.provider_connection_id, p.display_name,
                   p.model_identifier, p.position, p.enabled
            FROM council_participants p
            WHERE p.council_id = $1
            ORDER BY p.position, p.id
            """,
            council_id,
        )
    return [ParticipantRead(**dict(row)) for row in rows]


@council_router.post("/{council_id}/participants", response_model=ParticipantRead,
                     status_code=status.HTTP_201_CREATED)
async def add_participant(
    council_id: UUID,
    payload: ParticipantCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        council = await connection.fetchrow(
            "SELECT workspace_id FROM councils WHERE id = $1", council_id
        )
        if council is None:
            raise HTTPException(status_code=404, detail="Council not found")
        provider = await connection.fetchrow(
            """
            SELECT id FROM provider_connections
            WHERE id = $1 AND workspace_id = $2
            """,
            payload.provider_connection_id, council["workspace_id"],
        )
        if provider is None:
            raise HTTPException(status_code=404, detail="Provider connection not found")
        try:
            row = await connection.fetchrow(
                """
                INSERT INTO council_participants
                  (workspace_id, council_id, provider_connection_id, display_name,
                   model_identifier, position, enabled)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, council_id, provider_connection_id, display_name,
                          model_identifier, position, enabled
                """,
                council["workspace_id"], council_id, payload.provider_connection_id,
                payload.display_name, payload.model_identifier, payload.position,
                payload.enabled,
            )
        except Exception as exc:
            # Position conflicts are expected client errors; unrelated DB errors propagate.
            if getattr(exc, "sqlstate", None) == "23505":
                raise HTTPException(status_code=409, detail="Participant position is already used")
            raise
        await _append_event(
            connection, council["workspace_id"], "council.participant_added",
            {"workspace_id": str(council["workspace_id"]), "council_id": str(council_id),
             "participant_id": str(row["id"])},
            {"display_name": row["display_name"], "position": row["position"],
             "enabled": row["enabled"]},
        )
    return ParticipantRead(**dict(row))


@council_router.post("/{council_id}/runs", response_model=RunRead,
                     status_code=status.HTTP_202_ACCEPTED)
async def create_council_run(
    council_id: UUID,
    payload: RunCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=256)],
):
    canonical = json.dumps({"prompt": payload.prompt}, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async with database.tenant_transaction(principal.user_id) as connection:
        council = await connection.fetchrow(
            "SELECT id, workspace_id FROM councils WHERE id = $1", council_id
        )
        if council is None:
            raise HTTPException(status_code=404, detail="Council not found")
        workspace_id = council["workspace_id"]
        participants = await connection.fetchrow(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE p.enabled AND pc.status = 'active') AS ready
            FROM council_participants p
            JOIN provider_connections pc
              ON pc.workspace_id = p.workspace_id AND pc.id = p.provider_connection_id
            WHERE p.council_id = $1 AND p.workspace_id = $2
            """,
            council_id, workspace_id,
        )
        if participants["total"] == 0 or participants["ready"] == 0:
            raise HTTPException(
                status_code=409,
                detail="Council needs at least one enabled participant with an active provider connection",
            )

        inserted = await connection.fetchrow(
            """
            INSERT INTO idempotency_records
              (workspace_id, principal_id, operation, idempotency_key, request_hash)
            VALUES ($1, $2, 'council.run.create', $3, $4)
            ON CONFLICT (workspace_id, principal_id, operation, idempotency_key)
            DO NOTHING RETURNING id
            """,
            workspace_id, principal.user_id, idempotency_key, request_hash,
        )
        if inserted is None:
            existing = await connection.fetchrow(
                """
                SELECT request_hash, response_body FROM idempotency_records
                WHERE workspace_id = $1 AND principal_id = $2
                  AND operation = 'council.run.create' AND idempotency_key = $3
                FOR UPDATE
                """,
                workspace_id, principal.user_id, idempotency_key,
            )
            if existing is None or existing["request_hash"].strip() != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key reused with a different request")
            body = existing["response_body"]
            if body is None:
                raise HTTPException(status_code=409, detail="Matching request is still being finalized")
            if isinstance(body, str):
                body = json.loads(body)
            return RunRead(**body)

        run = await connection.fetchrow(
            """
            INSERT INTO council_runs (workspace_id, council_id, prompt, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id, workspace_id, council_id, status, outcome, created_at, updated_at
            """,
            workspace_id, council_id, payload.prompt, principal.user_id,
        )
        job = await connection.fetchrow(
            """
            INSERT INTO worker_jobs (workspace_id, run_id, job_type, payload)
            VALUES ($1, $2, 'council.run', $3::jsonb)
            RETURNING id
            """,
            workspace_id, run["id"], json.dumps({"run_id": str(run["id"])}),
        )
        result = RunRead(**dict(run), job_id=job["id"])
        await _append_event(
            connection, workspace_id, "council_run.queued",
            {"workspace_id": str(workspace_id), "council_id": str(council_id),
             "run_id": str(run["id"]), "job_id": str(job["id"])},
            {"status": "queued"},
        )
        await connection.execute(
            """
            UPDATE idempotency_records
            SET response_status = 202, response_body = $1::jsonb
            WHERE workspace_id = $2 AND principal_id = $3
              AND operation = 'council.run.create' AND idempotency_key = $4
            """,
            json.dumps(result.model_dump(mode="json")), workspace_id,
            principal.user_id, idempotency_key,
        )
    return result


@run_router.get("/{run_id}", response_model=RunRead)
async def get_council_run(
    run_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        row = await connection.fetchrow(
            """
            SELECT r.id, r.workspace_id, r.council_id, r.status, r.outcome, r.result,
                   r.created_at, r.updated_at, j.id AS job_id
            FROM council_runs r
            LEFT JOIN worker_jobs j ON j.run_id = r.id AND j.workspace_id = r.workspace_id
            WHERE r.id = $1
            """,
            run_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Council run not found")
    values = dict(row)
    if isinstance(values.get("result"), str):
        values["result"] = json.loads(values["result"])
    return RunRead(**values)


class RunCancellationRead(BaseModel):
    id: UUID
    status: str
    cancellation_requested: bool


@run_router.post("/{run_id}/cancel", response_model=RunCancellationRead)
async def cancel_council_run(
    run_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        row = await connection.fetchrow(
            """
            SELECT r.id, r.workspace_id, r.status, j.id AS job_id,
                   j.status AS job_status, j.cancel_requested_at
            FROM council_runs r
            LEFT JOIN worker_jobs j
              ON j.run_id = r.id AND j.workspace_id = r.workspace_id
            WHERE r.id = $1
            FOR UPDATE OF r
            """,
            run_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Council run not found")
        if row["job_id"] is None:
            raise HTTPException(status_code=409, detail="Council run has no worker job")

        run_status = row["status"]
        cancellation_requested = False
        event_type = None
        if row["job_status"] == "queued" and run_status == "queued":
            await connection.execute(
                """
                UPDATE worker_jobs SET status = 'cancelled', updated_at = now()
                WHERE id = $1 AND status = 'queued'
                """,
                row["job_id"],
            )
            await connection.execute(
                """
                UPDATE council_runs SET status = 'cancelled', updated_at = now()
                WHERE id = $1 AND status = 'queued'
                """,
                run_id,
            )
            run_status = "cancelled"
            event_type = "council_run.cancelled"
        elif row["job_status"] == "leased" and run_status == "running":
            if row["cancel_requested_at"] is None:
                await connection.execute(
                    """
                    UPDATE worker_jobs SET cancel_requested_at = now(), updated_at = now()
                    WHERE id = $1 AND status = 'leased' AND cancel_requested_at IS NULL
                    """,
                    row["job_id"],
                )
                event_type = "council_run.cancel_requested"
            cancellation_requested = True

        if event_type:
            await _append_event(
                connection, row["workspace_id"], event_type,
                {"workspace_id": str(row["workspace_id"]), "run_id": str(run_id),
                 "job_id": str(row["job_id"])},
                {"status": run_status, "cancellation_requested": cancellation_requested},
            )

    return RunCancellationRead(
        id=run_id, status=run_status,
        cancellation_requested=cancellation_requested,
    )
