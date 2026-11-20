import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from apps.api.auth import Principal, get_current_principal
from apps.api.database import Database


router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Workspace name cannot be blank")
        return normalized


class WorkspaceRead(BaseModel):
    id: UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    if not database.connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return database


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        rows = await connection.fetch(
            """
            SELECT id, name, description, created_at, updated_at
            FROM workspaces
            ORDER BY updated_at DESC, id
            """
        )
    return [WorkspaceRead(**dict(row)) for row in rows]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO workspaces (name, description, created_by)
            VALUES ($1, $2, $3)
            RETURNING id, name, description, created_at, updated_at
            """,
            payload.name,
            payload.description,
            principal.user_id,
        )
        await connection.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role)
            VALUES ($1, $2, 'owner')
            """,
            row["id"],
            principal.user_id,
        )
        await connection.execute(
            """
            INSERT INTO workspace_event_counters (workspace_id, last_sequence)
            VALUES ($1, 1)
            """,
            row["id"],
        )
        await connection.execute(
            """
            INSERT INTO workspace_events (workspace_id, sequence, event_type, resource, payload)
            VALUES ($1, 1, 'workspace.created', $2::jsonb, $3::jsonb)
            """,
            row["id"],
            json.dumps({"workspace_id": str(row["id"])}),
            json.dumps({"name": row["name"]}),
        )
    return WorkspaceRead(**dict(row))
