# Web client foundation

## Scope delivered

The initial React/TypeScript PWA shell provides a responsive navigation frame,
Council and individual-chat modes, a local-only composer preview, a backend
liveness indicator, an installable web manifest and a basic offline shell
fallback. It deliberately does not claim to provide real model conversations.

## Runtime topology

- `web`: static Vite build served by Nginx on port 8080.
- `api`: FastAPI on port 8000, internal to the Compose network.
- Nginx proxies `/api/*` to the API service, avoiding hard-coded browser
  service hostnames and enabling same-origin requests.
- `compose.yaml` starts both containers. It does not include PostgreSQL,
  durable workers, credentials or public ingress yet.

## Start

```sh
docker compose up --build
```

Open `http://localhost:8080`. The API status indicator should show online
when the API container is reachable. The API readiness endpoint remains 503
until real dependencies are implemented.

## Current limitations

No authentication, tenant persistence, provider connections, streamed model
responses, attachments, research execution or browser automation are wired.
The composer stores messages only in page memory and labels them as local
drafts. Offline support is a shell fallback, not offline chat synchronization.
