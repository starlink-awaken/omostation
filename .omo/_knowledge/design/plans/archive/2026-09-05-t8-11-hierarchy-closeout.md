---
schema_version: report/v1
type: report
title: BET-Y1Q4-T8-11 hierarchy closeout receipt
bet_id: BET-Y1Q4-T8-11
status: active
lifecycle: history
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T8-11 hierarchy closeout receipt

## Verify

```bash
PYTHONPATH=projects/cockpit/src python3 -m pytest -q projects/cockpit/tests/test_command_hierarchy.py
```

```
....                                                                     [100%]
4 passed in 0.34s
exit=0
```

## Digests

- test file `projects/cockpit/tests/test_command_hierarchy.py`: `sha256:d3da9306a38e85a4dbcaf849f4391cd27521721fa3a40bdc7bfbff6258af6d0c`
- note: CI bet-done gate resolves receipts on root checkout; submodule paths are not guaranteed present, so this root receipt binds the test digest.
