# Closeout — 2026-07-15 demo seed + setfacl design

## Landed
- ADR-0193: `c2g.demo_seed` deterministic OutcomeTracker fixture
- ADR-0194: setfacl design freeze (no host mutation)
- Tests: `tests/test_demo_seed.py`

## Ops
```bash
python -m c2g.demo_seed --data-dir runtime/c2g/outcomes --reset
# then open Wave2 panel or dashboard_export
```
