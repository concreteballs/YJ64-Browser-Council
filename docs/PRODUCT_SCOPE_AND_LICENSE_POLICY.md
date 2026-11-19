# Product scope and licensing / reuse policy

**Decision record:** 2026-11-19  
**Repository:** `concreteballs/YJ64-Browser-Council`  
**Working branch:** `research/initial-technical-audit`  
**Status:** MVP boundary and reuse rules frozen; project-license selection remains an explicit owner decision.

## 1. Repository baseline

- The repository is public and currently contains the README plus research, architecture, integration, roadmap and implementation-plan documents.
- The inspected working branch is `research/initial-technical-audit`.
- No root `LICENSE`, `COPYING`, `NOTICE`, dependency manifest, application source, or CI workflow was present in the inspected branch tree.
- The README already states that no project license has been selected and prohibits third-party source copying before approval.
- The repository's public visibility does not itself grant permission to reuse its source code. Until a license is deliberately selected and added, treat the project's code as not licensed for third-party reuse.

## 2. Project license and commercial distribution

**No project license is selected in this change.** This is intentional: choosing a license changes the owner's intellectual-property and distribution terms and must not be silently decided by an implementation agent.

Current safe position:
- Do not add a `LICENSE` file or claim that the project is MIT, Apache-2.0, proprietary, or otherwise licensed.
- Do not copy third-party source code into this repository.
- Do not promise that users or customers may redistribute, modify, or self-host the source under terms that have not been approved.
- Keep the product architecture commercially deployable and portable; architecture choices do not themselves grant source-code rights.

**Owner decision still required:** select the intended source distribution model (for example, proprietary/commercial, permissive open source, or another model) and approve the matching license text and contributor policy before the first public code release or third-party source import.

A permissive license such as MIT or Apache-2.0 can support commercial use and redistribution, but also grants broad rights to downstream users. A proprietary model preserves control over source distribution but requires clear customer deployment and usage terms. AGPL-style copyleft is a separate strategic choice, not a default. This record is a technical decision aid, not legal advice.

## 3. Third-party reference and reuse policy

### 3.1 Reference-only projects

The following audited projects are approved as architectural / behavioral references only. No source files, code snippets, artwork, branding, or bundled assets are approved for copying by this record:

- LibreChat
- Yes-Brainer
- Synode
- Multi-AI Chat Desktop
- Open WebUI

### 3.2 Approved library candidates (not yet imported)

These are candidates for normal dependency evaluation, not blanket approval to import arbitrary code or packages:

- Playwright — Apache-2.0; primary deterministic browser runtime candidate.
- Stagehand — MIT; optional higher-level browser interpretation layer.
- Browser Use — MIT; optional isolated autonomous browser worker.
- LiteLLM — MIT; optional provider normalization layer.
- LangGraph — MIT; optional orchestration aid.
- Temporal — MIT; later-stage durable workflow option.

Before adding any dependency, record its exact package/repository version, license, transitive-license report, notices, security posture and whether it is actually needed. Preserve upstream copyright and license notices. Re-check the license of the exact version and package being installed; repository-level summaries are not a substitute for package metadata.

### 3.3 Restricted or conditional candidates

- Yes-Brainer is AGPL-3.0. Do not copy or adapt its covered source into Browser Council unless the owner explicitly accepts the copyleft consequences after legal review.
- Open WebUI has a license/branding history. Do not fork, embed, or redistribute current code for a fully branded Browser Council product without reviewing the exact version's license and obtaining any required exception.
- Multi-AI Chat Desktop's MIT software license does not automatically cover separately noticed artwork or other third-party assets.

### 3.4 Required dependency controls

For every imported dependency:
1. Pin the exact version.
2. Record direct and transitive licenses.
3. Preserve copyright, license and NOTICE materials as required.
4. Track security advisories and update policy.
5. Keep product-specific code clearly separated from upstream code.
6. Do not copy code merely because it is publicly readable on GitHub.

## 4. Frozen MVP boundary

The first usable MVP is API-first and contains:

1. User-owned workspace(s) and tenant-safe resource ownership.
2. Individual conversations with at least two API provider adapters.
3. Persisted messages and conversation history.
4. Streaming responses and explicit cancellation.
5. One Council room/profile with a configurable participant roster.
6. Independent initial participant responses, recorded separately and combined in one Council view.
7. Basic critique/rebuttal and an explicit result that preserves disagreement; consensus must never be inferred from silence, timeout or provider failure.
8. Responsive web/PWA interface usable on phone and desktop.
9. Basic operational health, structured error states and safe server-side secret handling.

The MVP deliberately excludes:
- Browser Agent automation and authenticated provider web sessions.
- Autonomous research/search and evidence harvesting.
- Advanced voting/arbitration and elaborate multi-round synthesis beyond the minimal bounded Council flow.
- Public multi-tenant signup, billing, enterprise administration and production-scale quotas.
- YJ64 live production integration; only the compatibility contract is designed at this stage.
- Mobile native application; the web/PWA client is the first user interface.

These are later phases, not abandoned requirements.

## 5. Architecture boundaries retained

- API provider connections and authorized browser profiles remain different connection types.
- Browser Council owns its product UI, tenant-safe persistence and Council product workflow.
- Existing YJ64 model routing, native Council runtime, durable parent task queue and Engineering Core Gateway are not duplicated.
- Integration with YJ64 is through the documented, versioned `yj64.council-api.v1` contract.
- No neighboring repository is modified by this workstream.
- Secrets, API keys, cookies and browser storage state never enter source control, client bundles, logs or CI artifacts.

## 6. Batch A outcome

- [x] Working branch and repository baseline rechecked.
- [x] Existing license notices and root files checked; no project license or application/dependency files found in the inspected branch.
- [x] Third-party reference-only and dependency-candidate policy recorded.
- [x] API-first MVP boundary frozen.
- [ ] Owner selects the project's source license and commercial distribution terms.
- [ ] Before importing dependencies, exact versions and transitive notices are reviewed.

**Next:** Batch B — define stable resource identities, ownership, execution/outcome states, versioned API envelopes, event sequencing/idempotency/cancellation and the exact v1 compatibility mapping. The unresolved project-license choice does not require inventing a license or importing source code to proceed with schema design.
