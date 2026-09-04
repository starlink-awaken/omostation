---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: Internal-Only Surfaces Policy
type: doc
---
# Internal-Only Surfaces Policy

> **When NOT to expose a capability as cockpit CLI / Agora MCP / BOS URI.**  
> Complements `docs/operations/external-agent-attach-card.md`.

## Rule of thumb

Expose a **product channel** only if an external agent or human operator needs to **discover and invoke** it without reading the monorepo.  
Keep it **internal** if it is a gate, lock, worktree hygiene, type-debt sweep, or CI-only control plane.

## Internal by design (do not add BOS/MCP product APIs)

| Surface | Location | Why internal |
|---------|----------|--------------|
| PASW submodule isolation | `bin/gac/gac-worktree.sh`, ADR-0371 | Swarm hygiene; not a business capability |
| P79 partial-worktree reachability | `bin/gac/*`, GaC gates | CI/local gate correctness |
| pyright/ruff sweep tools | `bin/sweep/*`, workflow `pyright-sweep` | Engineering debt loop |
| agent-workflow locks/claims | `.omo/_delivery/agent-workflows/` | Control plane, not domain data |
| GaC validate/drift scripts | `bin/gac/gac-*.py` | Meta-governance |
| Submodule pointer transactions | `bin/ssot/submodule-pointer-transaction.sh` | Release hygiene |

These may still have **docs + skills + workflows** (how operators run them) without becoming `bos://…` routes.

## Product channels (must be discoverable)

| Surface | Expected channels |
|---------|-------------------|
| Knowledge search / research | cockpit + BOS `memory`/`analysis` + MCP via resolve |
| Governance state (OMO) | cockpit `omo` + BOS `governance` + omo MCP proxy |
| External channels inventory (ECCP) | `cockpit channels` + truth registry |
| KEMS control | `cockpit kems` + BOS `bos://memory/kems/*` |
| A2A / swarm | Agora MCP `a2a_*` / `swarm_*` |
| Capability discovery | `agora_capability_discover` + `cockpit discover` |

## Registered-but-not-ready

If a BOS row is `status: unimplemented` or `deprecated`:

1. It **must not** be in the default routable table (enforced in `bos_registry.py`).
2. Operators inspect via `cockpit bos list --all` or raw YAML.
3. Either implement to `active` or delete/archive the registration — do not leave silent traps.

## Decision checklist (before adding a channel)

1. Can an agent complete a real user job with only this entry?  
2. Is there already a BOS URI or MCP tool that should be reused?  
3. Will default discovery hide incomplete statuses?  
4. Is documentation updated in Attach Card / skills / capability-registry regen?
