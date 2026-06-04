# Debt Owner Routing Packet

Generated at: 2026-06-03T01:47:00Z

Owners: 2

Total routed items: 7

Lane counts: revalidate_now=0, schedule_now=2, escalate_now=0, continue_mitigation=0, watch_only=5

## Owner: sharedbrain-governance

Summary: 4 items; revalidate_now=0, schedule_now=2, escalate_now=0

### Schedule Now

- `SB_DECOMPOSITION` — missing_next_review_at — flags: none — `python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_DECOMPOSITION --next-review-at 2026-06-10T01:47:00Z`
- `SB_ROOT_CLEANUP` — missing_next_review_at — flags: none — `python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at 2026-06-10T01:47:00Z`

### Watch Only

- `SB_UNTESTED_PKGS` — upcoming_not_due — flags: none — `manual: keep item on review radar`
- `SB_BRIDGE_FIX` — upcoming_not_due — flags: none — `manual: keep item on review radar`

## Owner: omo-governance

Summary: 3 items; revalidate_now=0, schedule_now=0, escalate_now=0

### Watch Only

- `SB_ORPHANED_TASKS` — upcoming_not_due — flags: initial_review_required — `manual: keep item on review radar`
- `SB_PHASE17_PLAN` — upcoming_not_due — flags: none — `manual: keep item on review radar`
- `SB_PROJECTS_YAML` — upcoming_not_due — flags: none — `manual: keep item on review radar`
