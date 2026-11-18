# Open-source technical audit

**Audit date:** 2026-11-19  
**Scope:** source repositories, current READMEs/docs, selected implementation files and licenses.  
**Important:** This is a source-level reconnaissance, not a complete security audit, legal opinion, or proof that every project was built and exercised on a live machine.

## 1. Executive findings

There is no single project that already provides the complete YJ64 Browser Council requirement.

The strongest combination is:

1. **LibreChat** as a reference for a mature multi-provider web-chat product, user/workspace concepts, agent tools, MCP and deployment patterns. Do not adopt it wholesale as the Council engine.
2. **Yes-Brainer** as the closest reference for deliberation semantics: independent parallel answers, anonymous peer review, a judge, multi-round mediator-led consensus, and mobile-first PWA design. Its AGPL-3.0 license makes direct code reuse a deliberate copyleft decision.
3. **Multi-AI Chat Desktop** as the most relevant implementation reference for authorized, signed-in provider web sessions, isolated provider profiles, adapters, send/response confirmation, and recovery. Its MIT license is permissive, but the project is a Tauri desktop application and its feature scope is frozen.
4. **Playwright** as the deterministic browser runtime. Use it for browser contexts, pages, persistent profiles, reliable locators, traces and testable automation.
5. **Stagehand** as an optional higher-level layer on top of Playwright for unfamiliar page layouts; do not make natural-language actions the only control mechanism.
6. **Browser Use** as an optional autonomous browser/research agent, not the foundation of session isolation or the core Council state machine.
7. **LiteLLM** as a candidate API-provider normalization layer; **LangGraph** as an optional orchestration aid if a persisted graph becomes more valuable than a small explicit state machine.

The product should be an original, modular application. Reusing a complete existing chat product would create unnecessary coupling and would not satisfy the two-channel API/browser-session requirement.

## 2. Repository identity resolution

The original task listed names for three projects without specific repository URLs. The following repositories were identified as the best matching projects during this audit:

- Multi-AI Chat Desktop: https://github.com/TED-H-com/multi-ai-chat-desktop
- Yes-Brainer: https://github.com/trekhleb/yesbrainer
- Synode: https://github.com/mahatab/synode-council-of-ai-agents

If a different project was intended by any of those three names, it must be supplied and audited separately before any code is reused.

## 3. Comparison

| Project | License / commercial position | Architecture and actual strengths | Browser sessions | API / providers | Council and parallel work | Mobile / deployment | Recommendation |
|---|---|---|---|---|---|---|---|
| [Multi-AI Chat Desktop](https://github.com/TED-H-com/multi-ai-chat-desktop) | MIT for software. The commemorative artwork has a separate permission notice and is not automatically covered by MIT. | Tauri 2; isolated local WebView profile per provider; provider-specific adapters; workflow engine; snapshots/replay; explicit send and completion checks. README documents adapter breakage after provider UI changes and manual handling of challenges. | **Yes** — its defining feature is using the user's already-authorized signed-in provider pages. | Primarily browser UI automation; not a general multi-provider API gateway. | Parallel sends and structured workflows (Debate, Consult, Coding, Roundtable, Brainstorm). | Desktop Tauri application; separate browser extension. No general container-first hosted web app. Project describes the workflow feature set as frozen/maintenance-minded. | Best source-level reference for browser-session adapter design and reliability. Do not transplant the desktop architecture wholesale. |
| [Yes-Brainer](https://github.com/trekhleb/yesbrainer) | AGPL-3.0. Commercial use is possible under AGPL, but network deployment of a modified covered version carries source-availability obligations. Not a permissive-license shortcut for a closed SaaS. | Static TypeScript/Vite PWA; direct browser-to-provider requests with BYOK; IndexedDB/Dexie for council history; localStorage for keys/settings. Three deliberation structures: parallel, anonymous peer-voted Trial/Judge, and multi-round Mediator-led Consensus. | **No** — direct API calls, not authenticated provider web pages. | Anthropic, OpenAI, Google, Groq, OpenRouter, opt-in Ollama. | Excellent reference for independent opinions, anonymity, peer review, explicit convergence checks, visible disagreement and round caps. | Mobile-friendly installable PWA; static deployment; no server-side persistence or cross-device sync. Its own README says keys are stored in browser localStorage. | Best deliberation and mobile UX reference. Prefer independent implementation unless AGPL adoption is an intentional product decision. |
| [Synode](https://github.com/mahatab/synode-council-of-ai-agents) | MIT. | Tauri 2 + Rust backend + React/TypeScript frontend; shared provider layer; SSE streaming; OS credential store; local session persistence; optional Telegram bot. | **No** — provider APIs, not logged-in browser automation. | 8 cloud providers plus LM Studio/local models. | Independent parallel and sequential discussion, direct one-to-one chat, master-model verdict, follow-up @mentions, web search for supported providers. | macOS/Windows desktop app. Not a responsive hosted web product. | Useful reference for provider adapters, streaming, session models and UX; not the target deployment architecture. |
| [Open WebUI](https://github.com/open-webui/open-webui) | Current Open WebUI License includes a branding-preservation clause. The project says code through v0.6.5 remains BSD-3-Clause; later contributions use the newer terms. White-labeling at scale requires an exception or commercial license. | Self-hosted Python/backend + web frontend; local Ollama and OpenAI-compatible endpoints; extensible tools and knowledge features; Docker and Kubernetes deployment. | **No** — it connects model endpoints, not signed-in ChatGPT/Claude/Gemini web sessions. | Broad API-compatible and local model support. | Agents and tools exist, but it is not a ready-made multi-model debate/consensus engine. | Responsive web interface; Docker/Kubernetes. | Do not base a separately branded commercial YJ64 product on the current code without resolving the branding license. Study concepts only. |
| [LibreChat](https://github.com/LibreChat-AI/LibreChat) | MIT. | Large TypeScript/JavaScript monorepo; React SPA, Express/API packages, MongoDB, Redis-related deployment options, Docker/Helm. Multi-provider chat, auth, tools, MCP, agents, subagents, skills, web search, traces and APIs. | **No** — normal provider API integration, not automation of signed-in provider web UIs. | Broad cloud/local providers and custom OpenAI-compatible endpoints. | Agent chains and isolated subagents are useful building blocks, but the product is not itself a complete open multi-model Council with the required browser adapters. | Responsive web UI; Docker and Helm; designed for self-hosting and scaled deployments. | Strongest mature web-chat reference. Reuse patterns or small MIT components only after dependency and license review; avoid adopting the whole monolith as the Council core. |
| [Browser Use](https://github.com/browser-use/browser-use) | MIT for the open-source library. Hosted Browser Use Cloud is a separate commercial service. | Python browser-agent library; persistent agent REPL and Chrome DevTools Protocol; local browser or hosted cloud browser; Docker support. | **Yes** — browser sessions/profiles and authentication workflows are supported; hosted profile features are a separate service. | Uses an LLM to plan browser actions; supports local and remote browser operation. | Can perform autonomous browser tasks, but is not a multi-model Council or durable session database by itself. | Python library and hosted browser service; can be containerized. | Optional autonomous browser worker. Keep it behind an explicit, least-privilege tool boundary. |
| [Playwright](https://github.com/microsoft/playwright) | Apache-2.0. | Mature browser automation and test framework for Chromium, Firefox and WebKit; isolated browser contexts, storage-state reuse, locators, tracing and parallel execution. | **Yes** — persistent contexts and saved authenticated state are available. | No model-provider layer. | No Council logic; provides deterministic browser primitives and test automation. | Node.js, Python, Java and .NET libraries; container-friendly. | **Primary browser runtime** for the Browser Agent. |
| [Stagehand](https://github.com/browserbase/stagehand) | MIT. | TypeScript/Python/Go SDK built on Playwright; combines deterministic code with AI-driven act/observe/extract; supports previewing/caching actions. | **Yes**, through its Playwright/browser setup; it is not an account/session manager by itself. | LLM-assisted browser interpretation; provider credentials are needed for AI actions. | No Council engine. | SDK/library; can be used in a service. | Optional layer for unfamiliar page layouts. Prefer explicit Playwright locators for known workflows. |

## 4. Additional components worth evaluating

### LiteLLM — provider normalization

- Repository: https://github.com/BerriAI/litellm
- License: MIT in the current Python package metadata.
- Provides a unified API/SDK for 100+ model providers, common response formats, streaming, retries/fallbacks, routing, virtual keys, budgets and spend tracking.
- Suitable as a provider adapter or a separately operated gateway. It is not a Council protocol, browser automation system or session store.
- Before adopting the proxy in production, review its complete current license/dependency inventory, security posture, and which features are community versus enterprise.

### LangGraph — explicit stateful orchestration

- Python: https://github.com/langchain-ai/langgraph
- JavaScript: https://github.com/langchain-ai/langgraphjs
- License: MIT.
- Provides graph-based stateful agent execution, durable checkpoints, streaming and human-in-the-loop control.
- Useful if deliberation evolves into complex conditional research/review workflows. For the first MVP, a small explicit Council state machine backed by durable records may be simpler and easier to audit.

### Mastra — TypeScript agent/workflow framework

- Repository: https://github.com/mastra-ai/mastra
- Core uses Apache-2.0; directories named `ee/` use a separate Mastra Enterprise License.
- Has typed workflows, parallel/branch/loop execution, human approval, memory and subagents.
- Consider only if the product standardizes on a TypeScript backend. Review the license mapping per package before importing anything.

### Temporal — durable execution platform

- Repository: https://github.com/temporalio/temporal
- License: MIT.
- Provides long-running workflows that survive worker crashes and support retries/signals.
- Strong but operationally heavier than needed for the first release. Keep as a later scale/reliability option, not an MVP dependency.

## 5. License and reuse conclusions

| License | Commercial use | Main obligation / risk | YJ64 decision |
|---|---|---|---|
| MIT | Yes | Preserve copyright and license notices. | Preferred for small reusable components. |
| Apache-2.0 | Yes | Preserve notices/license; include NOTICE where applicable; patent terms apply. | Suitable for Playwright and other components after notice review. |
| AGPL-3.0 | Yes, but copyleft obligations apply to network use of modified covered software. | Users interacting over a network with a modified covered version must be offered corresponding source under AGPL terms. | Do not copy Yes-Brainer code into a closed hosted product unless this obligation is intentionally accepted and legally reviewed. |
| Open WebUI License (current) | The project permits many commercial deployments, subject to branding conditions. | Preserve prominent Open WebUI identity except specified exceptions; white-labeling at scale needs permission/license. | Not suitable as the foundation for a fully branded YJ64 SaaS without a separate licensing arrangement. |

Important distinctions:

- A public GitHub repository is not automatically reusable. The repository's actual license and notices govern.
- The Multi-AI Chat Desktop MIT license does not automatically cover its separately licensed commemorative artwork.
- Open WebUI has a multi-license history: do not assume that the current license applies retroactively to all historical contributions, or that the historical BSD-3 license applies to current code.
- Keep a dependency/license inventory and preserve upstream copyright notices. This audit is not legal advice.

## 6. Source-level observations that affect design

### Yes-Brainer

Its development notes describe a clear pipeline: fan out one turn to participants; either finish with independent answers, anonymize and collect peer votes before a Judge, or run repeated debate rounds with a Mediator deciding whether convergence has actually occurred. It persists completed events in IndexedDB and rehydrates after reload.

This is a strong reference for Council semantics, but its static-browser design deliberately has no server. It therefore does not provide server-owned multi-user workspaces, protected credential storage, durable cloud jobs, browser profile automation or cross-device session recovery.

### Multi-AI Chat Desktop

Its README describes one isolated local WebView profile per provider, explicit provider adapters, send acknowledgement and final-answer detection, retries for rejected sends, local transcript restoration, snapshots/replay, and diagnostics that exclude cookies and credentials. It also warns that provider DOM changes can break adapters and that real-account retests are distinct from CI.

This is the strongest practical reference for the browser-session track. It should inform the adapter contract and evidence requirements, not become the whole product.

### LibreChat

Its current architecture separates a React client, Express/API layer, shared schemas/data-provider packages and agent packages. Its agents package uses graph orchestration, streaming events, provider adapters, subagent handoffs and context management. The product also has mature deployment and multi-user patterns.

It is a large application with its own persistence and configuration assumptions. Embedding or forking all of LibreChat would duplicate product concerns and make YJ64 integration harder.

### Browser automation

Playwright should own deterministic browser lifecycle, isolation, page operations and evidence capture. Stagehand can add AI-assisted interpretation when selectors are unknown. Browser Use can be an optional autonomous worker. These tools should not be mixed into the Council's message/event store: browser actions are tools used by a Council participant, not the source of truth for Council state.

## 7. Audit conclusion

**Recommended composition:** original responsive web application + provider adapter registry + explicit Council orchestration/state machine + PostgreSQL-backed session/event store and queue + isolated Playwright browser workers + optional Stagehand/Browser Use + versioned YJ64-compatible API.

Reuse libraries and narrowly scoped patterns, not an entire product. Keep the API and browser-session provider types distinct, and never claim a browser interaction succeeded until the adapter verifies the actual submitted message and received response.

## 8. Primary sources

- https://github.com/TED-H-com/multi-ai-chat-desktop
- https://github.com/trekhleb/yesbrainer
- https://github.com/mahatab/synode-council-of-ai-agents
- https://github.com/open-webui/open-webui
- https://docs.openwebui.com/license/
- https://github.com/LibreChat-AI/LibreChat
- https://github.com/browser-use/browser-use
- https://github.com/microsoft/playwright
- https://github.com/browserbase/stagehand
- https://github.com/BerriAI/litellm
- https://github.com/langchain-ai/langgraph
- https://github.com/langchain-ai/langgraphjs
- https://github.com/mastra-ai/mastra
- https://github.com/temporalio/temporal
- https://supabase.com/docs/guides/functions/limits


## 9. Additional source and test inspection

The audit went beyond README descriptions and inspected selected implementation files and tests:

- **Multi-AI Chat Desktop:** `src-tauri/src/adapters.rs`, `src-tauri/src/webviews.rs`, `src/workflow/sendAndWait.ts`, `src/workflow/waitForResponse.ts`, `src/workflow/graph/executor.ts`, `src-tauri/src/session_checkpoint.rs`, and provider adapter JSON. Adapters are versioned data records with URL match rules, input/send/response selectors, login/logout/thinking detectors and timing. A bridge event keyed by provider/turn resolves the response waiter; provider reloads and timeouts reject it. The native host owns provider WebViews. **Important limitation found in source:** `runWorkflow` currently gates on one global `activeWorkflowRun`, and the checkpoint module writes one fixed `session-checkpoint.json` in the local app data directory. Thus the project is a valuable adapter/reliability reference, but it does not prove support for several independently durable Council runs in a hosted multi-tenant service. The CI and unit tests exercise workflow/adapter contracts; real provider UI behavior still needs live-account validation.

- **Yes-Brainer:** `use-council-session.ts`, `run-consensus-phase.ts`, `run-trial-phase.ts`, `storage/db.ts`, `storage/keys.ts`, and Playwright integration tests were inspected. The orchestrator fans out one stream per active seat and persists turn events in Dexie/IndexedDB. The consensus phase records progress after mediator rounds and re-answer fan-outs, then replays persisted progress on resume. A per-turn Web Locks guard prevents duplicate page execution where supported. The integration tests explicitly assert both convergence and round-cap termination without fabricated agreement. This is a strong implementation reference for phase separation, replay and test design. Its canonical data and API keys remain browser-local; it is not a cloud multi-tenant service.

- **Synode:** `crates/council-core/src/chat.rs`, provider implementations, `models/session.rs` and provider docs were inspected. Provider calls share an SSE parser and usage event model; provider-native web search is injected only for providers/models that support it. Session types distinguish Council and DirectChat. This is useful provider/streaming code, but its Rust/Tauri local desktop persistence and provider-API-only architecture do not provide hosted browser-profile automation.

- **LibreChat:** the `@librechat/agents` package README and repository package layout were inspected. It uses graph orchestration, streaming event handlers, provider adapters, tool execution, subagent handoffs, session JSONL records, and optional checkpoints/fork/clone operations. This confirms that its agent package can be studied independently from the full web product, subject to package dependency and license review.

These source findings reinforce the recommendation: take deliberation/replay ideas from Yes-Brainer, browser adapter patterns from Multi-AI Chat Desktop, provider/streaming patterns from Synode and LibreChat, but implement durable tenant-scoped run state and browser isolation specifically for Browser Council.
