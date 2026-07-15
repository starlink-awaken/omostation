---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0200 — operating-rhythm 接入 omo-doctor-cron

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

ADR-0199 put path-acl into `omo doctor`, but daily cron only ran workflow
status / governance-evolution / m4-health — ACL warnings were invisible unless
an operator manually ran doctor.

## Decision

1. Add `bin/gac/omo-doctor-cron.py` — runs doctor JSON, writes:
   - `runtime/cron/omo-doctor-latest.json`
   - `runtime/cron/omo-doctor-history.jsonl` (cap 90)
2. Extend `.omo/cron/operating-rhythm-crontab` daily **09:20** entry
3. One-line log summary includes `path-acl=` status
4. Exit 0 on warn-only; non-zero on doctor fail/error
5. Bootstrap checklist: `docs/operations/omo-bootstrap-checklist.md`

## Non-goals

- Auto `acl apply` from cron
- Replacing `omo watch`

## Verification

```bash
uv run --with pyyaml python bin/gac/omo-doctor-cron.py --json | head
python -m pytest tests/test_omo_doctor_cron.py -q
```

## References

- ADR-0199
- `.omo/cron/operating-rhythm-crontab`
- `docs/operations/omo-path-acl-runbook.md`
