# R77 Governance Audit — 2026-06-13

> Full governance, documentation, and configuration audit.
> Goal: keep the bus-foundation repo consistent and debt-free.

## Audit baseline (R77)

| Check | Result | Notes |
|-------|--------|-------|
| `ruff check` | 1 warning (B007 in `messagebus.py:27`) | R77 fix below |
| `TODO`/`FIXME`/`HACK` markers | 0 | clean |
| `from agora` imports | 0 | per ADR-0008 / D2 |
| `from typing import Callable` | 0 (post-R75) | `collections.abc` only |
| `from typing import Iterable/Iterator` | 0 (post-R75) | `collections.abc` only |
| Single file > 500 LOC | 0 (max 180) | per ADR-0008 |
| Unstaged changes | 0 (after R77) | clean |
| Tests | 59, 100% pass | no regressions |

## R77 actions (5 items)

### 1. Removed B007 warning (messagebus.py:27)

**Before**: `for sub_id, (pattern, callback) in ...` — `sub_id` unused
**After**: `for _sub_id, (pattern, callback) in ...` — ruff 0 errors

### 2. Removed duplicate GOVERNANCE.md

Two files existed: `GOVERNANCE.md` (root) and `docs/GOVERNANCE.md`.
Both were identical post-R75. **Deleted `docs/GOVERNANCE.md`** —
`GOVERNANCE.md` (root) is now the single source of truth.

### 3. Refreshed AGENTS.md

R73-R76 had added:
- 3 new backends (ws, realtime, persistent_bus)
- 1 new shared helper (pattern_match)
- 27 new tests (28 → 59)
- 1 patch version (0.1.0 → 0.1.1)
- New gotchas (`match_pattern`, `collections.abc`)

**R77 AGENTS.md** now reflects:
- 8 backends in key files table
- 16 test files in tests table
- 6 gotchas (was 4)
- "When to update this file" section (similar to GOVERNANCE.md)

### 4. Added ARCHITECTURE.md (new file)

First formal architecture document. Includes:
- C4-style diagram (Level 1-2)
- Component model (facade, router, envelope, DLQ, pattern_match, 8 backends)
- 5 explicit design decisions (D1-D5) with rationale + alternatives
- 6 anti-patterns (A1-A6) — explicit "don't do this" list
- 3 documented-but-not-implemented anti-patterns (out of scope for 0.1.x)
- Cross-repo consistency table (bus-foundation vs aetherforge-gateway vs kos)
- "Where the bus-foundation decisions live" pointer table

### 5. Updated GOVERNANCE.md decision log

Added 2 new entries (R76 0.1.1 patch + R77 governance audit). The
log now has 7 entries from R66 through R77, with explicit
"Source" column pointing to the relevant round number.

## Files changed in R77

| File | Change |
|------|--------|
| `AGENTS.md` | full rewrite (R77 truth) |
| `GOVERNANCE.md` | +2 decision log entries (R76, R77) |
| `docs/ARCHITECTURE.md` | NEW — 5-decision + 6-anti-pattern model |
| `docs/GOVERNANCE.md` | DELETED (duplicate) |
| `src/bus_foundation/backends/messagebus.py` | B007 fix (rename `sub_id` → `_sub_id`) |
| `.omo/_delivery/r77-governance-audit-2026-06-13.md` | this file |

## Verified invariants (R77)

- **Single file < 500 LOC**: max 180 (persistent bus.py)
- **Zero `from agora` imports**: 0 in `src/bus_foundation/`
- **No backend retry**: 0 (per RETRY-OWNERSHIP.md)
- **`ruff check`**: 0 errors (after B007 fix)
- **`from collections.abc` only**: 0 violations
- **No TODO/FIXME/HACK markers**: 0
- **59 tests, 100% pass**: no regressions
- **Public API frozen**: 0.1.1 since R76; 24-month compatibility promise
  (frozen for 24 months from 0.1.0 per GOVERNANCE.md)

## Backlog (deferred, NOT tech debt)

These are documented in `CHANGELOG.md` §"Backlog" and
`docs/ARCHITECTURE.md` §"Anti-patterns that are documented but
not yet implemented". They are **explicitly out of scope** for
the 0.1.x line:

- **R75-LOW-2**: trie-based dispatch (O(1) publish with N>100)
- **R73-LOW-ws**: real `websockets` transport (currently queue+hook shim)
- **Pydantic for Envelope**: simple class currently; Pydantic would
  add 1MB dep

## Why this is "debt-free" rather than "low-debt"

The R77 audit found 1 real warning (B007), 0 stale docs, 0 stale
configs, 0 TODOs. The repo is in a state where a new maintainer
can onboard by reading:
1. `AGENTS.md` (15 min) — file list, gotchas, release process
2. `GOVERNANCE.md` (10 min) — process, decision log
3. `docs/ARCHITECTURE.md` (20 min) — design decisions + anti-patterns
4. `docs/ADR-0003-no-l0-promotion.md` (5 min) — the L0 decision
5. `CHANGELOG.md` (10 min) — version history

In <1 hour, a new maintainer has full context. This is the
"debt-free" state — not zero work to do, but zero unexplained
work, zero hidden assumptions, zero "ask the original author"
moments.

## References

- `AGENTS.md` (R77)
- `GOVERNANCE.md` (R77)
- `docs/ARCHITECTURE.md` (R77, NEW)
- `CHANGELOG.md` (R76, with 0.1.0 + 0.1.1 + backlog)
- `CLAUDE.md` (R75)
- `docs/ADR-0003-no-l0-promotion.md` (R76)
- `docs/ADR-0002-phase-c-trigger-reality-DRAFT.md` (R70)
- `OWNERS.md` (R66)
- `pyproject.toml` (R76, 0.1.1)
