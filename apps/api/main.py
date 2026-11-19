from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(
    title="YJ64 Browser Council API",
    version="0.1.0",
    description="Cloud-first API foundation for Browser Council.",
)


@app.get("/api/v1/health/live", tags=["health"])
async def live():
    """Process liveness only; does not imply dependency readiness."""
    return {"status": "ok", "service": "browser-council-api"}


@app.get("/api/v1/health/ready", tags=["health"])
async def ready():
    """Readiness remains closed until database connectivity is implemented."""
    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "service": "browser-council-api",
            "dependencies": {
                "database": "not_implemented",
                "worker": "not_implemented",
            },
        },
    )
