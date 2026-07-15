---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0193 — Wave2 demo OutcomeTracker seed

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + c2g

## Context

Empty `runtime/c2g/outcomes` makes Wave2 UI/API show a blank baseline, which
blocks demos and operator training after ADR-0190/0191/0192.

## Decision

1. CLI `python -m c2g.demo_seed` writes a **deterministic** 6-pitch corpus
2. Default dir: `runtime/c2g/outcomes` (never `.omo/`)
3. Idempotent unless `--reset`
4. Corpus mixes success / partial / critical so heatmap + proposals activate
5. Non-goal: production analytics; this is **demo/fixture only**

## Verification

```bash
uv run --directory projects/c2g python -m c2g.demo_seed --data-dir /tmp/c2g-demo --reset --json
uv run --directory projects/c2g python -m c2g.dashboard_export --data-dir /tmp/c2g-demo --pretty | head
pytest projects/c2g/tests/test_demo_seed.py -q
```

## References

- ADR-0190 dashboard contract
- `projects/c2g/src/c2g/demo_seed.py`
