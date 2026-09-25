---
type: ephemeral
status: completed
created: 2026-09-20
---

# Gap Management System Retirement Decision

**Date**: 2026-09-20  
**Author**: governance-team  
**Status**: Implemented  
**Related Debt**: DEBT-20260917021531-GAP-SEED-DISPATCH  

## Executive Summary

The gap management system (gap-items, gap_registry, dispatch/campaign/reporting subdirectories) was never implemented despite being declared in `.omo/_truth/registry/debt.yaml`. This document records the decision to formally retire these declarations rather than implement them.

## Background

### Original Declaration (v1)

The debt ledger originally declared a complete gap management infrastructure:

```yaml
version: 1
gap_items_dir: .omo/debt/gap-items
gap_registry: .omo/debt/gap-registry.yaml
gap_seed_items:
  - .omo/debt/gap-items/META-01-OBSERVATION-MOS-BRIDGE.yaml
  # ... 27 items total
dispatch_ref: .omo/debt/dispatch/current.yaml
campaign_ref: .omo/debt/campaign/current.yaml
reporting_ref: .omo/debt/reporting/current.yaml
```

### Verification Findings (2026-09-16)

Full-catalog verification confirmed **all referenced paths physically absent**:

```bash
python3 -c "import os; paths = [...]; print(all(os.path.exists(p) for p in paths))"
# → False (0/31 paths exist)
```

Key observations:
1. `.omo/debt/gap-items/` never committed to git (`git log --all --diff-filter=A -- .omo/debt/gap-items/*` returns nothing)
2. `gap_registry.yaml`, `dispatch/`, `campaign/`, `reporting/` similarly never created
3. Code consumers handle missing paths gracefully:
   - `cockpit/observatory/strategy_sources.py`: `discover(..., required=False)` → empty_or_missing_directory
   - `projects/omo/src/omo/omo_debt_registry.py`: `registry.get(name, "")` fallback (lines 84-93)

## Options Analysis

### Option A: Build Complete Implementation

**Scope**: Implement all 27 gap seed items + dispatch/campaign/reporting subsystems  
**Effort**: ~28.5 person-days
- 27 gap items × 0.5 days each = 13.5 days
- Dispatch engine = 5 days
- Campaign manager = 5 days  
- Reporting dashboard = 5 days

**Pros**:
- Fulfills original architectural vision
- Complete gap tracking capability

**Cons**:
- Heavy upfront investment for unproven value
- System complexity vs actual need
- Opportunity cost (could fund real business bets)

**Verdict**: ❌ Over-engineering for unvalidated requirement

---

### Option B: Formal Retirement (Selected)

**Scope**: Remove all gap system declarations from SSOT  
**Effort**: ~2 person-days
- Update debt.yaml (version bump 1→2)
- Add REMOVED comments explaining rationale
- Close DEBT-20260917021531-GAP-SEED-DISPATCH with evidence
- Document decision in ADR

**Pros**:
- Aligns SSOT with reality (truth-driven engineering)
- Minimal effort, zero maintenance burden
- Eliminates confusion about "missing" files
- Follows P73 TRUTH-DRIVEN-ENGINEERING policy

**Cons**:
- Loses theoretical gap tracking capability
- Requires owner teams to self-report gaps manually

**Verdict**: ✅ Optimal given zero prior demand & graceful code fallbacks

---

### Option C: Minimal Implementation

**Scope**: Implement barebones gap registry only (no dispatch/campaign/reporting)  
**Effort**: ~3 person-days
- Simple YAML-based gap registry
- Manual item addition process

**Pros**:
- Some gap tracking capability
- Lower complexity than Option A

**Cons**:
- Still requires ongoing maintenance
- No automation advantage over manual tracking
- Partial implementation may create more confusion

**Verdict**: ❌ Unnecessary maintenance burden

---

## Decision

**Option B (Formal Retirement)** selected based on:

1. **Zero consumer demand**: All 3 scripts referencing gap-items handle absence gracefully (verify.py, autoloop-controller.py, governance-scanner.py)
2. **Never existed**: Paths were never created or committed — not "lost" but never born
3. **Code resilience**: omo_debt_registry.py already uses `registry.get(name, "")` pattern
4. **Opportunity cost**: 28.5 days could fund real business bets (Y1Q4 T3-04 knowledge flow + observability自愈)
5. **Truth-driven principle**: SSOT should reflect reality, not hypothetical capabilities

## Implementation

### Changes Made

1. **`.omo/_truth/registry/debt.yaml`**:
   - Version bumped: `1 → 2`
   - Removed fields: `gap_items_dir`, `gap_registry`, `gap_seed_items` (27 items)
   - Removed fields: `dispatch_ref`, `campaign_ref`, `reporting_ref`
   - Added REMOVED comments documenting rationale

2. **`.omo/debt/items/DEBT-20260917021531-GAP-SEED-DISPATCH.yaml`**:
   - lifecycle_state: `identified → resolved`
   - decision_needed: `null` (Option B selected)
   - evidence_refs: Updated to point to retirement documentation
   - history: Added 2026-09-20 resolve entry

3. **Verification**:
   ```bash
   python3 bin/ssot/verify.py
   # → 24/24 verified (100%)
   
   make gac-local-gate
   # → 57 checks ALL GREEN
   ```

## Impact Assessment

### Affected Systems

| System | Impact | Mitigation |
|--------|--------|------------|
| `bin/ssot/verify.py` | None | Already scans `.omo/debt/items/` (real registry) |
| `bin/ssot/autoloop-controller.py` | None | Prints stderr warning if GAP_DIR missing |
| `bin/ssot/governance-scanner.py` | None | Adds `debt.gap_source_present=false` metric |
| `projects/cockpit/.../strategy_sources.py` | None | `required=False` → empty_or_missing_directory |
| `projects/omo/src/omo/omo_debt_registry.py` | None | `registry.get(name, "")` → "" fallback |

### Net Effect

**Zero breaking changes**. All consumers already handle missing paths gracefully. Retirement merely aligns SSOT with this operational reality.

## Lessons Learned

1. **SSOT hygiene matters**: Declaring non-existent systems creates confusion and false expectations
2. **Graceful degradation is powerful**: Code that handles missing paths elegantly reduces technical debt pressure
3. **Build vs.摘除 decision**: When a system has zero prior demand and zero consumer impact, formal retirement beats implementation
4. **Version tracking**: Bumping version numbers when removing fields makes change history auditable

## References

- **Original debt registration**: DEBT-20260917021531-GAP-SEED-DISPATCH
- **Code fallback implementation**: projects/omo/src/omo/omo_debt_registry.py lines 79-93
- **Cockpit integration**: cockpit/observatory/strategy_sources.py line 482
- **Policy alignment**: P73-TRUTH-DRIVEN-ENGINEERING

---

**Approved by**: governance-team  
**Implemented in**: PR #4047  
**Next review**: N/A (resolved)
