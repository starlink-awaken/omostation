---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0199 — `omo doctor` 纳入 path-acl 日常节奏

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + omo

## Context

Scheme C 5c L1–L2 tools exist (`lint path-acl`, `acl plan/apply`) but were
opt-in CLI only. Daily doctor / watch / report did not surface ACL red flags.

## Decision

1. Add `_check_path_acl` to `omo doctor` (and thus `omo watch` / `omo report`)
2. Status mapping: world-writable / 0777 → **warn** (non-blocking exit)
3. Detail points operators to `omo acl plan --json`
4. Never mutates host from doctor
5. Ops runbook: `docs/operations/omo-path-acl-runbook.md`

## Non-goals

- Making path-acl a hard fail in CI by default
- Auto `apply` from doctor

## Verification

```bash
uv run --project projects/omo python -m omo.cli doctor --json
pytest projects/omo/tests/test_omo_doctor_path_acl.py -q
```

## References

- ADR-0187, ADR-0189, ADR-0198
- `omo_doctor._check_path_acl`
