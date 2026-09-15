---
schema_version: specification/v1
spec_version: 1.0.0
title: 3Y BET ledger schema hardening
bet_id: BET-Y1Q4-T10-167
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-15
last-reviewed: 2026-09-15
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# 3Y BET ledger schema hardening

## Background and problem

The 3Y BET ledger can be valid YAML while still being semantically unsafe:
BET-shaped mappings have previously been appended under unrelated root sections,
duplicate IDs can survive parsing, and malformed input errors do not identify
the source location well enough for a concurrent editor to repair the file.
`ledger-safe-insert.py` already provides the canonical insertion boundary, but
the loader and mutation path do not yet share a complete structural contract.

This spec makes the ledger fail closed on structural corruption while preserving
the existing transition, dependency, and completion-evidence semantics.

## Scope

- Validate the root mapping and the required top-level section types before any
  consumer reads BET data.
- Require BET entries to be mappings with `BET-*` IDs and reject duplicate IDs.
- Reject BET-shaped entries outside the `bets` sequence with a diagnostic naming
  the offending root section and entry ID.
- Report YAML parse failures with line, column, and bounded source context.
- Reuse the same structural validation from the loader, lint command, and
  `ledger-safe-insert.py`.
- Add focused regression tests for every failure class and the valid baseline.

## Non-goals

- Do not rewrite existing BET content unrelated to structural validation.
- Do not change transition, completion-evidence, or dependency semantics except
  where malformed structure must be rejected.
- Do not add a second ledger mutation utility or a parallel ledger SSOT.
- Do not auto-repair malformed YAML or silently relocate user-authored entries.

## Acceptance criteria

1. `python3 bin/plan/bet-ledger.py lint` remains green on the current ledger.
2. A malformed root shape, wrong root section type, duplicate BET ID, invalid
   BET entry type, or misplaced BET-shaped entry exits non-zero and names the
   repair location.
3. A YAML syntax error reports line, column, and at most a bounded context
   window; no fallback data is returned.
4. `ledger-safe-insert.py --dry-run` and the loader use the same structural
   validator and reject the same invalid fixtures.
5. Focused tests cover the baseline plus each negative case.

## Verification commands

```text
python3 bin/plan/bet-ledger.py lint
python3 -m pytest tests/unit/gac/test_ledger_safe_insert.py -q
```

## Anti-metrics

- Do not treat a YAML parse success as a semantic health signal.
- Do not measure success by the number of new validators, rules, or files.
- Do not use a synthetic or proxy ledger entry as evidence of production safety.

## Decision log

| # | Fork | Decision | Reason |
|---|---|---|---|
| 1 | Add a second writer versus reuse the existing inserter | Reuse `ledger-safe-insert.py` and expose one structural validator | Prevents mutation-path drift and keeps the write surface smaller |
| 2 | Auto-repair misplaced entries versus fail closed | Fail closed with an actionable diagnostic | Automatic relocation could change intent and hide concurrent edits |
| 3 | Normalize legacy content during this change versus preserve semantics | Preserve content and only enforce structure | Avoids unrelated ledger churn and protects downstream consumers |

## Rollback

Revert the validator and focused tests. The ledger remains readable by the
previous loader, and no existing BET transition data is rewritten by rollback.
