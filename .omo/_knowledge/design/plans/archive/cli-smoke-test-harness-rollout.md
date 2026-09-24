---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-24
---
# CLI smoke test harness rollout — BET-Y1Q4-T13

## Outcome

The Cockpit CLI availability probe is registered on the six-hour schedule
`15 */6 * * *`.  A regression in the covered core CLI surfaces is therefore
detectable within the required six-hour window instead of waiting for the
former daily run.

## Durable registration

- `.omo/cron/registry.yaml`: `cli-availability-probe-6h`, active, installed, crontab plane.
- `bin/_registry/scripts/governance/cli-availability-probe.yaml`: matching six-hour trigger, maturity `active`.
- `tests/test_cron_registry_contract.py`: regression test prevents a silent daily-schedule rollback.

## Operational result

- Local contract tests pass for both registry declarations.
- The canonical user crontab is updated from the daily token
  `omostation-cli-availability-probe-daily` to the six-hour token
  `omostation-cli-availability-probe-6h` after the tracked declaration passes local gates.
- Probe output continues to append the JSONL ledger under
  `runtime/probes/cli-availability.jsonl`; failures exit non-zero for human review.

## Boundary

This task covers scheduling and availability regression visibility only.  It does not
claim business value, alter Claims Authority admission, or add automatic repair.
