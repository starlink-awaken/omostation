---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0201 — Doctor-cron 状态 API + path-acl 连续 warn 告警

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + cockpit

## Context

ADR-0200 writes daily doctor snapshots to `runtime/cron/`. Operators still
needed: (1) cockpit consumption, (2) multi-day path-acl warn signal.

## Decision

1. `omo-doctor-cron` highlights gain:
   - `path_acl_warn_streak`
   - `path_acl_alert` when streak ≥ 3
2. API `GET /api/omo/doctor` loads latest + history_tail
3. Wave2 UI banner shows path-acl status / streak / ALERT
4. No auto remediation; hint remains `omo acl plan`

## Verification

```bash
python bin/gac/omo-doctor-cron.py
curl -s localhost:8090/api/omo/doctor | jq .highlights
pytest tests/test_omo_doctor_cron.py projects/cockpit/src/cockpit/tests/test_api_omo_doctor.py -q
```
