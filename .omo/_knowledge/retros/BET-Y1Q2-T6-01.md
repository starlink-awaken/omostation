---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: "BET-Y1Q2-T6-06 Retro: Dynamic GaC Rule Subtraction"
type: retro
---
# BET-Y1Q2-T6-06 Retro: Dynamic GaC Rule Subtraction

> completed_at: 2026-08-08
> bet_ref: BET-Y1Q2-T6-01
> actual_appetite: 1 day (plan was 1 week)

## What was done

### Phase A: Archive superseded rules (Day 1)
- 4 rules with `lifecycle: superseded` → `lifecycle: removed`
- CR-P76-6-2-MONITORING-CADENCE, CR-P76-6-5-LLM-DEFERRAL, CR-P77-2-1-PRINCIPLE-FORMALIZATION, CR-P77-2-2-CATALOG-SSOT
- Verified: `gac-validate.py --gate` passes (132 active, 4 removed)

### Phase B: Rule vitality tracking infrastructure (Day 1)
- **B1**: `bin/gac/gac-rule-gate-mapping.py` — maps 24/136 rules to gate checks via source_ref matching
- **B2**: `bin/gac/rule-vitality-tracker.py` — per-rule JSONL at `.omo/state/rule-vitality.jsonl`
- **B3**: Instrumented `gac-local-gate.py` `append_metrics()` + `gac-drift.py` to record vitality

### Phase C: Dynamic downgrade engine (Day 1)
- `bin/gac/rule-vitality-report.py` — zero-violations report, downgrade suggestions, apply-downgrade
- Safety guardrails: protected executors (hook_pre_edit), min 30d window, min 20 evals, max 3/week

## Key decisions

| Decision | Rationale |
|----------|-----------|
| JSONL for vitality storage | Append-only, no locking, easy to tail/grep |
| importlib.util for hyphenated modules | `rule-vitality-tracker.py` has hyphens, can't use regular import |
| Mapping via source_ref, not name matching | Rule IDs and gate check IDs have zero overlap; source_ref is the bridge |
| Proposal → approve model for downgrade | Never auto-modify governance-checks.yaml without human gate |
| 24/136 rules mapped (not 100%) | Remaining 112 rules are enforced indirectly (no dedicated gate check) |

## Verification

- `gac-validate.py --gate`: 0 error, 0 warning (132 active, 4 removed)
- `gac-drift.py`: 136 vitality entries recorded (1 per rule)
- `gac-local-gate.py --metrics`: 153 additional vitality entries from gate-mapped rules
- `rule-vitality-report.py --zero-violations`: 133 rules with 0 violations (correct)
- `rule-vitality-report.py --suggest-downgrade`: 0 suggestions (correct — need ≥20 evals)
- 12/12 unit tests pass

## Files changed

### New
- `bin/gac/rule-vitality-tracker.py` — vitality JSONL read/write
- `bin/gac/rule-vitality-report.py` — report + downgrade engine
- `bin/gac/gac-rule-gate-mapping.py` — rule↔gate mapping generator
- `.omo/_truth/registry/rule-gate-mapping.yaml` — mapping SSOT
- `tests/test_rule_vitality.py` — 12 tests

### Modified
- `.omo/_truth/registry/governance-checks.yaml` — 4 rules superseded→removed
- `bin/gac/gac-local-gate.py` — `_record_rule_vitality()` in `append_metrics()`
- `bin/gac/gac-drift.py` — `_record_drift_vitality()` after scan loop
- `docs/plans/3y-bet-ledger.yaml` — T6-01 status candidate→done

## Lessons learned

1. **Rule-gate mapping is sparse by design**: 24/136 rules have dedicated gate checks. The rest are enforced indirectly through broader checks. This is not a gap — it's the architecture.
2. **Vitality data takes time**: Need ≥20 evaluations over ≥30 days before suggesting downgrade. Can't rush data-driven decisions.
3. **importlib.util for hyphenated filenames**: Standard Python pattern for loading modules with hyphens in filenames. Cleaner than sys.path hacks.
4. **YAML multi-document parsing**: `governance-checks.yaml` has frontmatter + data docs. Must use `safe_load_all()` and iterate, not `safe_load()`.

## Next steps

- Run `gac-local-gate --metrics` regularly (CI already does) to accumulate vitality data
- After 30+ days, review `rule-vitality-report.py --suggest-downgrade` output
- Consider expanding mapping beyond source_ref (manual annotation for rules without direct gate checks)
