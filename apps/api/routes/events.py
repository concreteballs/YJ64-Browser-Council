import asyncio
import json
from datetime import datetime
from typing import Annotated, AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.auth import Principal, get_current_principal
from apps.api.database import Database
from apps.api.routes.workspaces import get_database


router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/events", tags=["workspace-events"])


class WorkspaceEventRead(BaseModel):
    id: UUID
    sequence: int
    event_type: str
    resource: dict
    payload: dict
    occurred_at: datetime


async def _verify_workspace(database: Database, principal_id: UUID, workspace_id: UUID) -> None:
    async with database.tenant_transaction(principal_id) as connection:
        row = await connection.fetchrow(
            "SELECT id FROM workspaces WHERE id = $1",
            workspace_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found")


async def _fetch_events(
    database: Database,
    principal_id: UUID,
    workspace_id: UUID,
    after_sequence: int,
    limit: int,
):
    async with database.tenant_transaction(principal_id) as connection:
        return await connection.fetch(
            """
            SELECT id, sequence, event_type, resource, payload, occurred_at
            FROM workspace_events
            WHERE workspace_id = $1 AND sequence > $2
            ORDER BY sequence
            LIMIT $3
            """,
            workspace_id,
            after_sequence,
            limit,
        )


@router.get("", response_model=list[WorkspaceEventRead])
async def replay_workspace_events(
    workspace_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    await _verify_workspace(database, principal.user_id, workspace_id)
    rows = await _fetch_events(database, principal.user_id, workspace_id, after_sequence, limit)
    return [WorkspaceEventRead(**dict(row)) for row in rows]


@router.get("/stream")
async def stream_workspace_events(
    workspace_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
):
    cursor = 0
    if last_event_id:
        try:
            cursor = int(last_event_id)
            if cursor < 0:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=422, detail="Last-Event-ID must be a non-negative sequence")
    await _verify_workspace(database, principal.user_id, workspace_id)

    async def generate() -> AsyncIterator[str]:
        deadline = asyncio.get_running_loop().time() + 55
        last_keepalive = asyncio.get_running_loop().time()
        current_cursor = cursor
        while asyncio.get_running_loop().time() < deadline:
            if await request.is_disconnected():
                break
            rows = await _fetch_events(
                database, principal.user_id, workspace_id, current_cursor, 100
            )
            for row in rows:
                event = dict(row)
                current_cursor = event["sequence"]
                payload = {
                    "event_id": str(event["id"]),
                    "workspace_id": str(workspace_id),
                    "sequence": event["sequence"],
                    "event_type": event["event_type"],
                    "resource": event["resource"],
                    "payload": event["payload"],
                    "occurred_at": event["occurred_at"].isoformat(),
                }
                yield (
                    f"id: {current_cursor}\n"
                    f"event: {event['event_type']}\n"
                    f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
                )
            now = asyncio.get_running_loop().time()
            if not rows and now - last_keepalive >= 15:
                yield ": keep-alive\n\n"
                last_keepalive = now
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
