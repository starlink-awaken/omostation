---
title: Batch2 D1 KOS quality deepening (≥50 sample)
date: 2026-07-24
type: audit
batch: 2
---

# KOS quality + retrieval baseline

- sampled: **50** docs (repo knowledge surfaces: audits/decisions/plans/docs)
- clean: **43**
- issues: **7**
- clean_rate: **0.86**
- measured_documents pointer (goals): see `.omo/_truth/goals/current.yaml` (Batch1 remeasure 5193)

## Retrieval hit-rate baseline (keyword in sample)

| query | hits | n | hit_rate |
|-------|------|---|----------|
| G-DEL | 3 | 50 | 0.06 |
| ADR-0232 | 0 | 50 | 0.0 |
| role_framework | 1 | 50 | 0.02 |
| schedule_harness | 0 | 50 | 0.0 |
| physical | 2 | 50 | 0.04 |

## Fixes applied this batch

- Documented broken links list for follow-up (no silent mass rewrite of unrelated vault)
- Baseline stored for 2027Q2 graph PoC

## Issues (sample)

```json
[
  {
    "path": ".omo/_knowledge/decisions/0107-phase3-bos-contract-linter.md",
    "problems": [
      "very_many_h1_maybe_dup"
    ]
  },
  {
    "path": "docs/SUBMODULE-PR-REVIEW-GUIDE.md",
    "problems": [
      "very_many_h1_maybe_dup"
    ]
  },
  {
    "path": ".omo/_knowledge/decisions/0005-architecture-p29-upgrade.md",
    "problems": [
      "very_many_h1_maybe_dup"
    ]
  },
  {
    "path": ".omo/_knowledge/audits/2026-06-15-model-driven-p5-closeout.md",
    "problems": [
      "very_many_h1_maybe_dup"
    ]
  },
  {
    "path": "docs/2026-07-10-bus-foundation-r89-r97-spec.md",
    "problems": [
      "broken_link:../ARCHITECTURE-DETAILED-MAP.md",
      "broken_link:../GOVERNANCE-EVOLUTION-ROADMAP.md",
      "broken_link:../VISION-ROADMAP.md",
      "broken_link:../ARCHITECTURE-DETAILED-MAP.md",
      "broken_link:../ARCHITECTURE-DETAILED-MAP.md"
    ]
  },
  {
    "path": ".omo/_knowledge/decisions/0120-runtime-health-semantics-fix.md",
    "problems": [
      "broken_link:../../projects/runtime/src/runtime/scheduler.py",
      "broken_link:../../projects/omo/src/omo/omo_state_schema.py",
      "broken_link:../../../runtime/matrix.yaml",
      "broken_link:../../../runtime/scheduler_state.json",
      "very_many_h1_maybe_dup"
    ]
  },
  {
    "path": ".omo/_knowledge/decisions/0128-state-generation-concurrency.md",
    "problems": [
      "very_many_h1_maybe_dup"
    ]
  }
]
```
