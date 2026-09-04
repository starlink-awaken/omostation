---
type: ephemeral
created: 2026-09-03
---

# Phase 2 Retrospective — Cockpit Governance Context and Domain Bindings

> Date: 2026-08-11
> Scope: Documents content-plane convergence, Task 3 and the Workspace half of Task 3A
> Accepted upstream: `omostation-cockpit` PR #35, merge `815bfea47e6829509276271ef9b55e833d8390ca`

## Outcome

Cockpit again exposes a truthful, read-only governance view over the actual owners instead of importing the removed `cockpit.scripts.cockpit_mcp` compatibility module:

- Workspace phase, status, wave, and theme come from Workspace state and goals; the goals `theme` is authoritative when present;
- all 12 Documents domains come from the formal L4 `ManifestRegistry` and the canonical Documents registry;
- `domain_context(domain_id)` preserves L4 identity and adds the optional Workspace capability binding without copying domain paths or metadata;
- CARDS list/check delegate to OMO and preserve owner exit codes and violations;
- KEMS status delegates content classification to L4 and reports OMO/Kairon reachability without inventing health;
- the existing Cockpit MCP server now exposes `workspace_context`, `domains_list`, `domain_context`, `cards_status`, `cards_check`, and `kems_status`;
- CLI, dashboard, and health surfaces use the same adapter and no longer show a green success message when the result is degraded.

The accepted Cockpit suite passed with 1,138 tests and 10 existing warnings. GitHub lint and test jobs both passed before merge. A Critical/Important-only review concluded Ready Yes.

## SSOT Decision

The machine chain is now executable, not only documented:

```text
Documents L4 registry + DOMAIN.yaml
  -> L4 ManifestRegistry
  -> Cockpit governance_context
  -> Cockpit MCP domain_context
  -> thin client gateway in the opened domain
```

The Workspace binding registry records only capability and client bindings. It references domain IDs from L4 and rejects missing, unknown, or duplicate coverage through `documents-domain-project-check.py`; it does not become a second domain registry.

## Verification Evidence

- focused Cockpit governance tests: 52 passed;
- full Cockpit suite: 1,138 passed;
- Ruff check and format: clean;
- GitHub CI: lint and test passed;
- live checkout smoke: Workspace context available, 12/12 domains present, six governance MCP tools registered, `domain_context(vault)` bound to `content-domain`, OMO CARDS check exit 0;
- KEMS correctly returned degraded/non-zero because the current Documents audit still contains 44,534 violations.

## What Worked

1. **One adapter, many projections.** CLI, dashboard, and MCP share the same owner-aware envelopes, which removes three opportunities for SSOT drift.
2. **Binding instead of duplication.** Workspace can guide Skills, Workflows, tasks, and knowledge runtime without copying Documents identity or execution code.
3. **Truthful degraded state.** Existing content debt remains visible while the new control plane itself can be accepted and merged.
4. **Review constrained to user impact.** One review found one real human false-success issue; fixing that was useful. The review stopped after Critical/Important cleared.
5. **Deterministic tests.** System Map no longer passes or fails based on stale workflow events on the developer machine, and the test no longer writes to a live Workspace event path.

## Efficiency Adjustment

This is currently a single-user local system. Delivery therefore optimizes for useful convergence:

- block on data loss, unexpected writes, static traversal, false-success, broken SSOT links, focused/full test failures, and CI failures;
- record hostile same-host syscall timing races, exhaustive platform combinations, speculative abstractions, and repeated no-new-evidence review loops as hardening debt;
- prefer a small owner adapter and stable envelopes over a new service, duplicated client configuration, or domain-local runtime.

## Remaining Debt

- The installed user-level Cockpit entry still needs to be refreshed from the accepted checkout and smoked after the root pointer lands.
- A full KEMS status scans the current Documents content plane and is too expensive for frequent UI polling; add caching only after a measured interactive need.
- 44,534 current audit violations are migration inventory, not a Cockpit defect; later waves must classify or migrate them.
- The 12 domain-root client gateways have not yet been updated. That batch changes client behavior and requires exact path confirmation before writing.
- ChatGPT web cannot consume local Codex MCP configuration; it remains out of local-project scope until a reviewed remote plugin exists.

## Next Phase

1. Merge the root pointer, Workspace binding registry, checker, plan, and phase evidence.
2. After explicit batch-write confirmation, make the 12 registered domain gateways thin projections and remove stale domain-local runtime instructions.
3. Smoke at least `vault`, `work-weijian`, and `creative` as standalone local projects through the same Workspace MCP.
4. Continue with the machine migration registry before moving or deleting any Documents assets.
