# Debt Owner Routing Packet

Generated at: 2026-06-27T12:00:00Z

Owners: 1

Total routed items: 8

Lane counts: revalidate_now=8, schedule_now=0, escalate_now=0, continue_mitigation=0, watch_only=0

## Owner: omo-self-healing

Summary: 8 items; revalidate_now=8, schedule_now=0, escalate_now=0

### Revalidate Now

- `auto-r1-1782094852` — stale_due_item — flags: initial_review_required, escalation_watch — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-r1-1782094852 --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- `auto-r2-1782094852` — stale_due_item — flags: initial_review_required, escalation_watch — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-r2-1782094852 --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- `auto-test-1782094852` — stale_due_item — flags: initial_review_required, escalation_watch — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-test-1782094852 --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- `auto-test-1782094861` — stale_due_item — flags: initial_review_required, escalation_watch — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-test-1782094861 --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- `auto-r1-error` — stale_due_item — flags: initial_review_required — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-r1-error --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- `auto-r2-error` — stale_due_item — flags: initial_review_required — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-r2-error --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- `auto-test-any` — stale_due_item — flags: initial_review_required — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-test-any --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- `auto-test-error` — stale_due_item — flags: initial_review_required — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id auto-test-error --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
