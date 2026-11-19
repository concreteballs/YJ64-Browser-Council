# YJ64 Browser Council

Independent, multi-model research and deliberation environment for the YJ64 ecosystem.

## Project status

**Phase 1 — research and contract definition.** Source audit and architecture are documented. Batch A has frozen the API-first MVP boundary and third-party reuse policy; API/event contracts are next. Application implementation has not started.

## Documents

- [Open-source technical audit](docs/RESEARCH_AUDIT.md)
- [Architecture decision proposal](docs/ARCHITECTURE_DECISION.md)
- [YJ64 Engineering Core integration](docs/YJ64_INTEGRATION.md)
- [Implementation roadmap](docs/IMPLEMENTATION_ROADMAP.md)\n- [Product scope and licensing / reuse policy](docs/PRODUCT_SCOPE_AND_LICENSE_POLICY.md)

## Non-negotiable boundaries

- This repository is the only repository in which Browser Council implementation work is authorized.
- Other YJ64 repositories may be inspected read-only for compatibility; they must not be modified without separate approval.
- Do not begin product implementation until the audit and architecture decisions are reviewed.
- API integrations are the default. Browser automation is an optional, explicitly authorized adapter.
- Never bypass authentication, CAPTCHA, paywalls, rate limits, or provider security controls.
- Keep provider credentials and browser session data out of source control, logs, task payloads, and public artifacts.
- A model's agreement is not evidence of truth. Preserve dissent, uncertainty, evidence provenance, and test boundaries.

## License

No project license has been selected yet. Do not add a license file or copy third-party source code until the owner approves the project's licensing strategy and third-party notice process.
