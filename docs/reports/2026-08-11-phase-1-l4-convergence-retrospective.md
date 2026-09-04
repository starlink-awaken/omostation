---
type: ephemeral
created: 2026-09-03
---

# Phase 1 Retrospective — L4 Content Boundary and Declarative Domains

> Date: 2026-08-11
> Scope: Documents content-plane convergence, Tasks 1–2
> Accepted upstream: `omostation-l4-kernel` PR #4, merge `e5d92646a114c11bb98a29a9959d2dca157029a6`

## Outcome

Phase 1 established a machine-verifiable boundary between Documents content and Workspace execution:

- governed historical source material can be declared with `CONTENT_ARCHIVE.yaml` without being mistaken for live runtime;
- invalid manifests, inventory drift, active consumers, special files, and ordinary symlink drift converge to stable `L4-CONTENT-011` evidence;
- domain bootstrap is declarative-only and publishes `DOMAIN.yaml`, method, profile, ontology, and rubric documents;
- legacy bootstrap remains compatible but no longer creates `_runtime`, `_control`, daemon, MCP, executable, or cache assets;
- CLI and lifecycle envelopes no longer claim success when audit or migration fails;
- the final L4 suite passed with 491 tests passed and 5 platform skips, and all required GitHub CI jobs passed before merge.

## SSOT Decision

The stable knowledge-domain identity chain is:

```text
@公共/_control/L4-DOMAIN-REGISTRY.yaml
  -> <domain>/DOMAIN.yaml
  -> Cockpit/Workspace MCP runtime projection
  -> human/client projections (DOMAIN-INDEX.md, CLAUDE.md, AGENTS.md)
```

`DOMAIN-INDEX.md` and client instruction files are projections. They must not become independent registries. Documents owns content and domain-local declarations; Workspace owns execution, governance, skills, workflows, tasks, and generated runtime state.

## What Worked

1. **Contract before migration.** Building the archive and domain contracts before moving data prevented filename-based classification from deleting or relocating historical code material.
2. **Truthful degradation.** Stable issue/envelope behavior made missing owners and audit drift observable instead of silently green.
3. **Submodule-first delivery.** Merging l4-kernel before changing the root pointer prevented the root repository from referencing an unavailable child commit.
4. **Linux/macOS CI.** A Linux inode-reuse test failure exposed a non-portable test assumption; replacing unlink/recreate with atomic replacement fixed the evidence without changing production semantics.
5. **Explicit authority split.** L4 validates content contracts; it does not execute domain KEMS runtime.

## What Was Too Expensive

The Task 2 review loop spent disproportionate time on adversarial same-host, exact-syscall-window replacement races. Those concerns are valid for a hostile multi-tenant runtime, but the current deployment is a single-user local system. They delayed useful convergence without changing the normal operating outcome.

The delivery bar is therefore revised:

- still blocking: data loss, unexpected writes, static symlink traversal, false-success envelopes, broken SSOT linkage, failed focused/full tests, failed CI;
- backlog hardening: hostile local inode/ancestor swaps timed between syscalls, exhaustive platform matrices, speculative abstraction, and repeat audits without new evidence.

One implementation review plus one whole-branch review is sufficient when the focused suite, full suite, lint, and CI are green.

## Remaining Debt

- Path-based ancestor traversal and the generic manifest loader are not fully fd-anchored against a malicious same-host race.
- Archive hashing buffers a file before combining its inventory hash; benchmark and stream it before scanning very large active archives.
- Some legacy Documents gateway text still instructs execution of scripts under `_runtime` or `_control`; these references must be removed as consumers migrate.
- At the Phase 1 close, the Workspace/Cockpit MCP entry was broken by imports of the removed `cockpit.scripts.cockpit_mcp`; Cockpit PR #35 repaired it in Phase 2.

## Next Phase

1. Restore Cockpit context, domains, CARDS, health, and KEMS from their real Workspace/L4/OMO owners.
2. Expose the same read-only governance context through the existing Cockpit MCP server.
3. Add a Workspace-owned domain-project binding registry and `domain_context` tool so each Documents domain can be opened independently in Claude, ChatGPT/Codex, Zed, or similar Cowork clients.
4. Keep per-client `CLAUDE.md` / `AGENTS.md` files thin and generated or validated; capabilities remain Workspace-owned.
