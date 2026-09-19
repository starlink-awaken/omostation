---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-08-24



bet_id: BET-Y1Q3-T1-09
type: ssot
last_updated: 2026-09-03
---

# Escape-hatch solidification — permission class vs fingerprint debt

> Status: accepted
> Date: 2026-08-21
> BET: BET-Y1Q3-T1-09
> ADR: ADR-0422

## Problem

D4 already allowlists `SWARM_ESCAPE_ID` and writes `.omo/_delivery/swarm-escape/`. The ledger is write-only. 66 records are all `ci_local_skip`. 44 reuse `submodule-reachability-partial-worktree` to skip **ci-local-fast** (not reachability). 22 reuse `emergency-human-hotfix` from agent paths; YAML `requires_human: true` is not enforced. Pre-existing gate failures therefore persist: agents skip, nobody owns a fingerprint, nothing crystallizes.

## Decision log (grill-me)

| # | Fork | Ruling | Why |
|---|---|---|---|
| 1 | Govern the ticket or the failure? | **C**: `escape_id` is a permission class; fingerprint is the debt identity | A is gamed by switching IDs; B drops the permission model |
| 2 | How to get fingerprints? | **C**: observe-then-skip; fingerprint = `(surface, check_id, signature)` | Skip currently never runs the preflight, so the ledger cannot cluster |
| 3 | What may a class skip? | **D**: new failures that touch this diff and are not known-debt block; unrelated-to-diff or unexpired known-debt may skip; baseline shadow then shrink-only | Empty baseline must not lock main (ADR-0380) |
| 4 | `requires_human` | **D + narrow C**: shim/`swarm-git`/`AGENT_ID` reject `emergency-human-hotfix`; system git with empty `AGENT_ID` allowed; single-use token exception | YAML already declared human; 22 agent uses prove A/B fail |
| 5 | Overheat sink | **D**: after shadow-end, same fingerprint ≥3 / 7d must sink before skip again; class spray quota as backstop; owner follows the check not the skipper | Digest-only rots like the current 66 |
| 6 | Old IDs | **C + no init expansion**: split classes; deprecated aliases expire on shadow-end | `CI_LOCAL_SKIP` never skipped reachability; AGENT-BRIEF §1.4 forbids INIT_ALL |
| 7 | Known-debt home | **C**: `.omo/_truth/registry/gate-known-debt.yaml`; ruff / layer-call stay inner baselines | Do not duplicate ruff into skip-layer |
| 8 | Wave 1 cut | **D**: full mechanism, `mode: shadow`; human-ID fail-closed immediately; GitHub out | Flip is a registry line after 7d + digest + owned known-debt |
| 9 | Accompanying item | **D**: classify missing-submodule as `uninitialized-submodule:*`; docs stop teaching `--no-verify` for pre-existing debt | Init-all already default and contradicts BRIEF |

## Architecture

```
preflight (always on CI_LOCAL_SKIP / wrapper --no-verify push)
    → fingerprints
    → permission class (surfaces + fingerprint_allow)
    → skip policy (new vs unrelated vs known-debt)
    → shadow: would-block is logged, hook still exits 0
    → human class: deny on agent path unless single-use token
    → record JSON includes fingerprints + actor, not whitelist reason only
digest --dry-run clusters ledger; does not mutate allowlist
```

### Permission classes

- `partial-worktree` — only `uninitialized-submodule:*`
- `local-preflight-preexisting` — unexpired known-debt or unrelated-to-diff on `ci-local-fast` / `pointer-drift`
- `pointer-drift` — pointer-drift surface only
- `write-owner-repair-draft` — `no_verify_commit` / pre-commit (unchanged)
- `emergency-human-hotfix` — requires human or consumed token
- `submodule-reachability-partial-worktree` — deprecated alias of `partial-worktree` until 2026-08-28

### Fingerprint

`surface` ∈ {`ci-local-fast`, `pre-commit`, `pointer-drift`} (`github` reserved).
`check_id` is the producer or `uninitialized-submodule:<producer>`.
`signature` is a stable short hash of producer + normalized excerpt (no timestamps).

Inner ruff / layer-call baselines remain inside those gates. A ruff failure is `kind=inner-baseline` and is not skip-layer known-debt.

### Skip policy (shadow)

Allow skip when:

1. class permits the flag and surface, and
2. each fingerprint is either `uninitialized-submodule:*` under `partial-worktree`, or in unexpired known-debt, or does not touch `changed_paths` (global checks need known-debt), and
3. not overheated after shadow-end.

Otherwise `decision=would_block` in shadow (`ok=True` for the hook) or `deny` after flip. Human-ID mismatch is `deny` even in shadow.

### Known-debt

New file, skip-layer only. Fields: `fingerprint, surface, check_id, signature, owner, expires_at, seeded_from_escape, active`. Growth only via sink. Wave 1 ships empty / schema only.

### Overheat

After `skip_policy.shadow_end` (2026-08-28): same fingerprint key ≥3 records in 7 days → `sink_required`. Sink = fix / known-debt with owner+expiry / SOFT with owner+expiry. Class spray quota counted in the same helper.

## Non-goals

GitHub admin-merge, flipping shadow→fail in this landing, INIT_ALL, sealing human system-git `--no-verify`, auto-writing `SOFT_CHECKS` without an owner.
