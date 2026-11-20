import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from apps.api.auth import Principal, get_current_principal
from apps.api.database import Database
from apps.api.routes.workspaces import get_database


provider_router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/provider-connections", tags=["provider-connections"])
conversation_router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/conversations", tags=["conversations"])
message_router = APIRouter(prefix="/api/v1/conversations/{conversation_id}/messages", tags=["messages"])


class ProviderConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=80)
    connection_type: Literal["api", "browser_session"]


class ProviderConnectionRead(BaseModel):
    id: UUID
    name: str
    provider: str
    connection_type: str
    status: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    provider_connection_id: UUID
    system_instructions: str = Field(default="", max_length=20000)


class ConversationRead(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    provider_connection_id: UUID
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    client_message_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=100000)
    idempotency_key: str = Field(min_length=8, max_length=256)


class MessageRead(BaseModel):
    id: UUID
    client_message_id: str
    conversation_id: UUID
    role: str
    content: str
    status: str
    sequence: int
    created_at: datetime


@provider_router.get("", response_model=list[ProviderConnectionRead])
async def list_provider_connections(
    workspace_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        rows = await connection.fetch(
            """
            SELECT id, name, provider, connection_type, status, created_at
            FROM provider_connections
            WHERE workspace_id = $1
            ORDER BY created_at, id
            """,
            workspace_id,
        )
    return [ProviderConnectionRead(**dict(row)) for row in rows]


@provider_router.post("", response_model=ProviderConnectionRead, status_code=status.HTTP_201_CREATED)
async def create_provider_connection(
    workspace_id: UUID,
    payload: ProviderConnectionCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO provider_connections
              (workspace_id, name, provider, connection_type, created_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, provider, connection_type, status, created_at
            """,
            workspace_id,
            payload.name.strip(),
            payload.provider.strip(),
            payload.connection_type,
            principal.user_id,
        )
    return ProviderConnectionRead(**dict(row))


@conversation_router.get("", response_model=list[ConversationRead])
async def list_conversations(
    workspace_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        rows = await connection.fetch(
            """
            SELECT id, workspace_id, title, provider_connection_id, created_at, updated_at
            FROM conversations
            WHERE workspace_id = $1
            ORDER BY updated_at DESC, id
            """,
            workspace_id,
        )
    return [ConversationRead(**dict(row)) for row in rows]


@conversation_router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    workspace_id: UUID,
    payload: ConversationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
):
    async with database.tenant_transaction(principal.user_id) as connection:
        connection_row = await connection.fetchrow(
            """
            SELECT id FROM provider_connections
            WHERE id = $1 AND workspace_id = $2
            """,
            payload.provider_connection_id,
            workspace_id,
        )
        if connection_row is None:
            raise HTTPException(status_code=404, detail="Provider connection not found")

        row = await connection.fetchrow(
            """
            INSERT INTO conversations
              (workspace_id, title, provider_connection_id, system_instructions, created_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, workspace_id, title, provider_connection_id, created_at, updated_at
            """,
            workspace_id,
            payload.title.strip(),
            payload.provider_connection_id,
            payload.system_instructions,
            principal.user_id,
        )
        await connection.execute(
            """
            INSERT INTO conversation_counters (workspace_id, conversation_id, last_sequence)
            VALUES ($1, $2, 0)
            """,
            workspace_id,
            row["id"],
        )
    return ConversationRead(**dict(row))


@message_router.get("", response_model=list[MessageRead])
async def list_messages(
    conversation_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
    after_sequence: int | None = None,
    limit: int = 50,
):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    async with database.tenant_transaction(principal.user_id) as connection:
        rows = await connection.fetch(
            """
            SELECT id, client_message_id, conversation_id, role, content, status, sequence, created_at
            FROM messages
            WHERE conversation_id = $1
              AND ($2::bigint IS NULL OR sequence > $2)
            ORDER BY sequence
            LIMIT $3
            """,
            conversation_id,
            after_sequence,
            limit,
        )
    return [MessageRead(**dict(row)) for row in rows]


@message_router.post("", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: UUID,
    payload: MessageCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Database, Depends(get_database)],
    idempotency_header: Annotated[str, Header(alias="Idempotency-Key")],
):
    if idempotency_header != payload.idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key header must match request body")

    canonical = json.dumps(
        {"client_message_id": payload.client_message_id, "content": payload.content},
        sort_keys=True,
        separators=(",", ":"),
    )
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async with database.tenant_transaction(principal.user_id) as connection:
        conversation = await connection.fetchrow(
            "SELECT workspace_id FROM conversations WHERE id = $1",
            conversation_id,
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        workspace_id = conversation["workspace_id"]

        inserted = await connection.fetchrow(
            """
            INSERT INTO idempotency_records
              (workspace_id, principal_id, operation, idempotency_key, request_hash)
            VALUES ($1, $2, 'message.create', $3, $4)
            ON CONFLICT (workspace_id, principal_id, operation, idempotency_key) DO NOTHING
            RETURNING id
            """,
            workspace_id,
            principal.user_id,
            payload.idempotency_key,
            request_hash,
        )
        if inserted is None:
            existing = await connection.fetchrow(
                """
                SELECT request_hash, response_body
                FROM idempotency_records
                WHERE workspace_id = $1 AND principal_id = $2
                  AND operation = 'message.create' AND idempotency_key = $3
                FOR UPDATE
                """,
                workspace_id,
                principal.user_id,
                payload.idempotency_key,
            )
            if existing is None or existing["request_hash"].strip() != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key reused with a different request")
            response_body = existing["response_body"]
            if response_body is None:
                raise HTTPException(status_code=409, detail="Matching request is still being finalized")
            if isinstance(response_body, str):
                response_body = json.loads(response_body)
            return MessageRead(**response_body)

        counter = await connection.fetchrow(
            """
            UPDATE conversation_counters
            SET last_sequence = last_sequence + 1
            WHERE conversation_id = $1 AND workspace_id = $2
            RETURNING last_sequence
            """,
            conversation_id,
            workspace_id,
        )
        if counter is None:
            raise HTTPException(status_code=409, detail="Conversation sequence counter is missing")

        row = await connection.fetchrow(
            """
            INSERT INTO messages
              (workspace_id, conversation_id, client_message_id, role, content, status, sequence)
            VALUES ($1, $2, $3, 'user', $4, 'completed', $5)
            RETURNING id, client_message_id, conversation_id, role, content, status, sequence, created_at
            """,
            workspace_id,
            conversation_id,
            payload.client_message_id,
            payload.content,
            counter["last_sequence"],
        )
        result = MessageRead(**dict(row))
        await connection.execute(
            """
            UPDATE idempotency_records
            SET response_status = 201, response_body = $1::jsonb
            WHERE workspace_id = $2 AND principal_id = $3
              AND operation = 'message.create' AND idempotency_key = $4
            """,
            json.dumps(result.model_dump(mode="json")),
            workspace_id,
            principal.user_id,
            payload.idempotency_key,
        )
    return result
