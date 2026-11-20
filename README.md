# YJ64 Browser Council

Independent, multi-model research and deliberation environment for the YJ64 ecosystem.

## Project status

**Phase 2 — cloud-first foundation.** Batches A and B are complete. The FastAPI service and responsive React/TypeScript PWA shell are in place. CI now builds both containers and validates Compose; the PostgreSQL tenant schema and RLS regression test pass in CI; the API now has an asyncpg pool lifecycle and transaction-local tenant context. Provider-neutral OIDC verification and initial protected workspace list/create routes are implemented and tested. Provider metadata, conversation creation, ordered message history and idempotent user-message persistence are implemented. A durable PostgreSQL worker queue foundation is now implemented with leases, heartbeats, bounded retries, expired-lease recovery and a dedicated least-privilege worker function boundary. A typed queue client and database smoke tests are included. A tenant-scoped cancellation API is now implemented: queued jobs cancel immediately, while leased jobs receive a durable cancellation request that the worker must acknowledge. Council profiles and participant rosters can now be created and listed. Idempotent Council run creation atomically persists a run, an identifier-only queue job, a workspace event and its idempotency response; it requires at least one enabled participant with an active provider connection. Run status/result lookup and a run-level cancellation endpoint are available; leased work remains running until the worker acknowledges cancellation. A continuously running worker, the worker-owned run lifecycle now transitions claimed runs to running and requires an explicit allowed analytical outcome plus a persisted JSON result before completion. A continuously running worker, provider execution and model-token streaming remain pending. Durable workspace event replay and SSE reconnection are now implemented.

## Documents

- [Open-source technical audit](docs/RESEARCH_AUDIT.md)
- [Architecture decision proposal](docs/ARCHITECTURE_DECISION.md)
- [YJ64 Engineering Core integration](docs/YJ64_INTEGRATION.md)
- [Implementation roadmap](docs/IMPLEMENTATION_ROADMAP.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Product scope and licensing / reuse policy](docs/PRODUCT_SCOPE_AND_LICENSE_POLICY.md)
- [Internal API and event contracts](docs/API_AND_EVENT_CONTRACTS.md)
- [Contract validation workflow](.github/workflows/contract-validation.yml)
- [Web client foundation and runtime topology](docs/WEB_CLIENT_FOUNDATION.md)
- [Data model and tenant security](docs/DATA_MODEL_AND_TENANT_SECURITY.md)
- [API database lifecycle](docs/API_DATABASE_LIFECYCLE.md)
- [Authentication boundary](docs/AUTHENTICATION_BOUNDARY.md)
- [Workspace API](docs/WORKSPACE_API.md)
- [Conversation and message API](docs/CONVERSATION_API.md)
- [Durable worker queue](docs/WORKER_QUEUE.md)

## Non-negotiable boundaries

- This repository is the only repository in which Browser Council implementation work is authorized.
- Other YJ64 repositories may be inspected read-only for compatibility; they must not be modified without separate approval.
- Do not begin product implementation until the contract-validation workflow passes and remaining owner decisions are recorded.
- API integrations are the default. Browser automation is an optional, explicitly authorized adapter.
- Never bypass authentication, CAPTCHA, paywalls, rate limits, or provider security controls.
- Keep provider credentials and browser session data out of source control, logs, task payloads, and public artifacts.
- A model's agreement is not evidence of truth. Preserve dissent, uncertainty, evidence provenance, and test boundaries.

## License

No project license has been selected yet. Do not add a license file or copy third-party source code until the owner approves the project's licensing strategy and third-party notice process.
