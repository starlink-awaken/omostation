---
type: ephemeral
created: 2026-09-03
---

# T10-64 Automation Fallout Repair — Delivery Report

Date: 2026-08-29 · Bet: BET-Y1Q3-T10-64 · Spec: `docs/superpowers/specs/2026-08-29-t10-58-automation-fallout-repair-design.md`

## What broke

| # | Symptom | Root cause |
|---|---------|-----------|
| 1 | `bin/agent-workflow.py` crashed (`No module named 'omo.workflow.omo_shared'`) — red-line toolchain down since 09:35 | Local-only extraction commit `847200ac` used a sibling-relative import for package-root `omo_shared`, and referenced `datetime`/`UTC` without importing them |
| 2 | `import omo.omo_audit_checks` failed (circular import) | Local-only extraction commit `8a816dbe`: `omo_audit.py` ↔ `omo_audit_checks.py` top-level import cycle |
| 3 | 163 untracked placeholder drafts in `.omo/_knowledge/decision-proposals/` | `tests/unit/test_resident_decision.py` isolated `PROPOSAL_DIR` but **not** `INBOX_DIR`; every pytest run leaked 5 fixture drafts (filenames match fixture data exactly: `trace-abc`, `evt-fallback`, `event`, `trace-StepFailed`, `trace-StepTimeout`) during unattended test cycles |
| 4 | Repeated chore(state) commit → reset-to-origin/main churn on local main (3× today, all commits orphaned) | Agent sessions commit state-sync snapshots directly on main; branch protection rejects the push; a later step resets main to origin/main. Governed path is worktree+PR (#2519 precedent) |

## Fixes delivered

1. **omo child branch (local, commits `34b0eaa7` + `cb9c8f59`, push deferred — see follow-ups)**
   - `workflow/diagnostics_p74.py`: parent-relative `..omo_shared` import; `from datetime import UTC, datetime`; unused `Path` removed.
   - `omo_audit.py`: `governance_check_*` imports moved into `run_governance_audit`; PEP 562 `__getattr__` preserves the `__all__` re-export; both import orders verified.
2. **omo subtree (this PR, on clean origin base)**
   - `resident/decision.py::_decide`: drop provenance-free trigger events; at most one draft per `(event_type, trace_id)` per UTC day (JSON-content comparison, not filename only).
   - `tests/unit/test_resident_decision.py`: fixture now isolates `INBOX_DIR` (leak fixed); empty-provenance contract flipped to drop; same-day dedupe tests. 7/7 pass.
3. **commit-msg guard (this PR)**
   - `.githooks/commit-msg`: rejects `chore(state)*` commits on local `main` with worktree+PR guidance; `SWARM_ESCAPE_ID` bypass (D4). Installed to `.git/hooks/` and live-tested: rejection fires on main, bypass works.
4. **Noise disposition (workspace state plane, not a git change)**
   - Deleted 13 empty-trace placeholder drafts; kept 85 real proposals + 12 DEC-* lifecycle docs. Inbox 110 → 97. (Count had already fallen 163 → 110 to a concurrent cleaner.)
5. **Protocol / agent awareness**
   - AGENTS.md §1.3: chore(state)-on-main ban with rationale and escape hatch.
   - Agent memory entry for future sessions.

## Verification

- `uv run --with pyyaml python bin/agent-workflow.py status` → `agent-workflow status: ok` (bootstrap/status/compliance all clean).
- `cd projects/omo && uv run python -c "import omo.omo_audit_checks, omo.omo_audit, omo.workflow.diagnostics_p74"` → exit 0 (both import orders).
- `uv run pytest tests/unit/test_resident_decision.py -q` → 7 passed.
- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → only the 2 pre-existing T1-12 errors.
- Guard live test on local main: `git commit --allow-empty -m "chore(state): …"` → rejected with guidance; `SWARM_ESCAPE_ID=…` → proceeds.

## Follow-ups (owned)

1. **omo child reconciliation** (rebase local line onto origin/main #112-114+, push, submodule-pointer transaction) — blocked on the unattended extraction session ("Blueprint Test") still being active (last commit 15:32 during this bet). Resume trigger: session idle ≥ 2h or ended. Its commits `c3a56973`/`847200ac`/`8a816dbe`/`6fe958c6` + repairs `34b0eaa7`/`cb9c8f59` are recoverable via `projects/omo` local reflog.
2. **Resident ledger WAL growth** — `runtime/omo/event-ledger.sqlite3-wal` at 4.1MB without checkpoint; investigate long-lived reader connections in the next maturity window. The 15:10 lock failure was judged an extreme concurrency burst (WAL + busy_timeout ≥ 5000ms + retry budget already in place from T10-48), not a code defect.
3. **make install-hooks** target referenced by `.githooks/README.md` no longer exists; hooks were installed manually this time — either restore the target or fix the doc.
