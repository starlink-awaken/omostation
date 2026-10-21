# GOAL-04 FIX-01: Canonical SceneCard Parser Closeout

**BET ID**: `BET-Y2Q4-T10-340401`
**Date**: 2026-10-21
**Branch**: `agent/codex/BET-Y2Q4-T10-340401-parser`
**Base HEAD**: `e5823c0ac99d4e4986b6310a2186ab1af135a9b9`
**Status**: Engineering complete, awaiting commit/push authorization.

## Scope

Implemented the shared SceneCard YAML parser at `lib/scene_card_document.py` and
migrated three callers to use it:

| Caller | Change |
|--------|--------|
| `bin/ssot/scene-card-review.py` | validate/promote/status use shared parser; promote writes back via shared sync+write |
| `bin/ssot/scene-card-lifecycle.py` | `_load_yaml_scene_card`, `transition_scene_card`, `activate` use shared parser; write-back via shared sync; timestamp updated for Python 3.9 compatibility |
| `bin/ssot/gen-scene-card-lineage.py` | `_load_scene_card_body` uses shared parser; ambiguous YAML propagates as typed error |

## Root-Cause Fixes Applied

### Mirror Write-Back

The initial `sync_declared_mirrors` implementation assigned the new value to
`document.body[key]` before comparing against the frontmatter mirror.  The
comparison then saw the already-updated body value (e.g. `assisted`) and the
old frontmatter value (e.g. `shadow`), concluded they differed, and skipped the
mirror sync.  Fixed by capturing `original_body_value` before mutation and
using it for the mirror-detection comparison.

### Python 3.9 Make Compatibility

The Makefile `scene-card-check` target uses the system Python (3.9), not the
project venv (3.14).  The lifecycle script imported `datetime.UTC` (3.11+),
causing all Make-driven lifecycle checks to fail at import.  Replaced with
`datetime.timezone.utc` to preserve the existing Make aggregate gate.

## Test Results

Ledger verify command:

```
python3 -m pytest tests/test_scene_card_document.py tests/test_scene_card_parser_callers.py \
  tests/test_scene_card_lifecycle_check.py tests/scene_v2/test_scene_card_registry_connector.py \
  -q -p no:randomly
```

Result: **42 passed in 0.27s**.

Module path check confirmed parser loads from the current checkout:
`/Users/xiamingxing/ws-v34-goal04-parser-impl/lib/scene_card_document.py`.

| Environment | Version |
|-------------|---------|
| Interpreter | Python 3.14.7 (`.venv/bin/python3`) |
| PyYAML | 6.0.3 |
| pytest | 9.1.1 |

## Boundary Compliance

- No production SceneCard files, projections, or broker/lease/authority state touched.
- No lifecycle admission rules or readiness semantics changed.
- All modified files are within the ledger `write_surfaces` list.
- No commit, push, force, or hook bypass performed.
- Operational and value axes remain `NOT_PROVEN`; no deployment or production
  adoption is claimed.

## Remaining Work

- User confirmation required for `git commit` and `git push`.
- Independent verification (Clone B frozen diff / blind handoff) has not yet been
  performed; this closeout is authored by the implementation agent and should
  be treated as engineering-verified only, not independently audited.
