# Cockpit CLI import performance recheck — BET-Y1Q4-T15

## Result

PASS. The historical 164 ms regression is no longer present.

## Fresh-process measurements

Six fresh Python processes imported `cockpit.cli` after inserting the Cockpit
`src` path. The samples were:

- 28.6 ms
- 31.7 ms
- 26.2 ms
- 29.3 ms
- 27.9 ms
- 26.8 ms

All samples are below the 120 ms task budget and the relaxed CI ceiling.

## Focused regression

```text
PYTHONPATH=src python3 -m pytest -q tests/test_fast_path.py
4 passed
```

`test_fast_path_telemetry_end_to_end` was included in the same file.  The
implementation therefore meets the original fast-path acceptance and the
relaxed CI contract without changing the budget.

## Boundary

This is a read-only recheck and dashboard truth reconciliation.  No runtime,
CLI, test budget, value evidence, or Claims Authority state was changed.
