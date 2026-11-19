# API foundation

This is the initial FastAPI process boundary. It intentionally exposes only
liveness and readiness endpoints; no authentication, tenant data, provider
calls or Council execution is implemented yet.

- `/api/v1/health/live`: confirms the HTTP process is responding.
- `/api/v1/health/ready`: returns 503 until database and worker dependency
  checks are implemented and verified.

Start locally:

```sh
python -m pip install -r requirements-api.txt
uvicorn apps.api.main:app --reload
```
