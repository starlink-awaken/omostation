# BET-Y1Q2-T6-06 Retro: Skill Auto-Crystallization Engine

**Status**: done
**Completed**: 2026-08-08
**Appetite**: 3 days
**Actual**: ~0.5 day

## Goal

When MOS belief records accumulate >= 2 per topic, automatically crystallize them into reusable Agent Skill packages at `.agents/skills/<topic>/SKILL.md`.

## What Was Done

### 1. Core Module: `omo_crystallizer.py`
- Created `projects/omo/src/omo/omo_crystallizer.py` as the library module
- `SkillCrystallizer` class with `check_and_crystallize()` method
- Supports both single-topic (auto-trigger) and batch (CLI) modes
- Enhanced SKILL.md generation: includes pitfalls, solutions, beliefs, scope contexts
- Threshold constant: `CRYSTALLIZATION_THRESHOLD = 2`

### 2. Auto-Trigger Integration
- Added `_try_auto_crystallize()` to `MOSBeliefManager.record_belief()`
- Best-effort: never raises exceptions (wrapped in try/except)
- Fires after state write + audit log, before return
- Logs `AUTO_CRYSTALLIZE` to audit trail on success

### 3. CLI Wrapper Update
- Updated `bin/gac/skill-crystallizer.py` to import from `omo.omo_crystallizer`
- Added `--check` flag for dry-run (report only, no writes)
- Added `--json` flag for machine-readable output
- Fixed sys.path to correctly resolve omo package

### 4. Tests
- 10 new tests in `projects/omo/tests/test_omo_crystallizer.py`
- Coverage: threshold logic, idempotency, auto-trigger, lessons/contexts inclusion, batch scan
- All 29 tests pass (10 new + 19 existing MOS closed-loop)

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Library module in omo package | Reusable by MOSBeliefManager, not just CLI |
| Best-effort auto-trigger | Matches pattern from adjudication belief feedback |
| Idempotent crystallization | Don't overwrite if belief count already in SKILL.md |
| Enhanced SKILL.md format | Include lessons, contexts, not just beliefs |

## Verification

```
projects/omo/tests/test_omo_crystallizer.py: 10/10 PASSED
projects/omo/tests/test_mos_closed_loop.py: 19/19 PASSED (no regression)
CLI --check mode: correctly reports ready/waiting topics
CLI execution mode: crystallized workflow:bet-execution skill
```

## Lessons Learned

1. **Path resolution matters**: `bin/gac/` scripts need explicit `sys.path` manipulation to find `projects/omo/src/`. The parents[1] calculation was wrong initially (pointed to `bin/` not workspace root).

2. **Idempotency via content check**: Rather than tracking state, check if the belief count already appears in the existing SKILL.md. Simple and effective.

3. **Best-effort pattern is powerful**: The auto-trigger silently catches all exceptions, ensuring belief recording never fails due to crystallization issues. This matches the adjudication feedback pattern.

## Files Changed

- `projects/omo/src/omo/omo_crystallizer.py` (new, ~170 lines)
- `projects/omo/src/omo/omo_belief.py` (added `_try_auto_crystallize` method)
- `bin/gac/skill-crystallizer.py` (rewritten as CLI wrapper)
- `projects/omo/tests/test_omo_crystallizer.py` (new, 10 tests)
- `docs/plans/3y-bet-ledger.yaml` (status: candidate → done)
- `.omo/tasks/planned/bet-y1q2-t6-06.yaml` (status: candidate → done)

## Next Steps

- Monitor crystallization in production as more beliefs accumulate
- Consider adding `--update` flag to force-regenerate existing skills
- Track which crystallized skills are actually used by agents
