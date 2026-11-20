import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from apps.api.database import Database
from apps.api.routes.conversations import (
    conversation_router,
    message_router,
    provider_router,
    job_router,
)
from apps.api.routes.workspaces import router as workspaces_router


database = Database(os.getenv("DATABASE_URL"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    app.state.database = database
    try:
        yield
    finally:
        await database.close()


app = FastAPI(
    title="YJ64 Browser Council API",
    version="0.1.0",
    description="Cloud-first API foundation for Browser Council.",
    lifespan=lifespan,
)


@app.get("/api/v1/health/live", tags=["health"])
async def live():
    """Process liveness only; does not imply dependency readiness."""
    return {"status": "ok", "service": "browser-council-api"}


@app.get("/api/v1/health/ready", tags=["health"])
async def ready():
    """Readiness requires a reachable database and a future worker service."""
    database_ready = False
    if database.connected:
        try:
            database_ready = await database.ping()
        except Exception:
            database_ready = False

    dependencies = {
        "database": "ready" if database_ready else "not_configured_or_unavailable",
        "worker": "not_implemented",
    }
    if database_ready and dependencies["worker"] == "ready":
        return {"status": "ready", "service": "browser-council-api", "dependencies": dependencies}

    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "service": "browser-council-api",
            "dependencies": dependencies,
        },
    )

app.include_router(workspaces_router)
app.include_router(provider_router)
app.include_router(conversation_router)
app.include_router(message_router)
app.include_router(job_router)
