---
bet_id: BET-Y1Q4-T6-20
status: done
completed_at: 2026-09-06T01:50:00+00:00
run_id: 20260906T013733Z-bet-execution-01a20e92
pr: https://github.com/starlink-awaken/omostation/pull/3265
---

# Retro: BET-Y1Q4-T6-20 — E-DOC 双平面边界门禁落地

## What Delivered
- `bin/gac/check-documents-boundary.py`: Unified boundary gate (E-DOC-001~005)
- `tests/test_documents_boundary_check.py`: 29 pytest tests
- `governance-checks.yaml`: CR-EDOC-001~005 registered
- `bin/_registry/scripts/governance/check-documents-boundary.yaml`: Script registry entry

## What Went Well
- Clear spec from ADR-0191 made implementation straightforward
- 29 tests pass on first real run (after yaml import fix)
- Diagnostic Envelope with self-heal suggestions works out of the box
- Script correctly detects 31992 historical violations (validates detection accuracy)

## What Was Hard
- `import yaml` at module level caused test failures — pyyaml not in uv venv
- YAML syntax errors from unquoted colons in governance-checks.yaml descriptions
- bin-quota-diff CI gate required script_baseline increment
- CI preflight blocks pushes even for pre-existing failures (cockpit-ui dist)

## Lessons
1. **Lazy imports for optional deps**: Always lazy-import pyyaml in scripts that may run in minimal venvs
2. **Quote YAML values with colons**: `bos_routed: true` in descriptions must be quoted
3. **Script baseline tracking**: New bin scripts require baseline increment in governance-checks.yaml
4. **CI preflight is comprehensive**: Use SWARM_ESCAPE_ID=local-preflight-preexisting for known-debt bypasses

## Follow-up
- E-DOC-001~005 are now DESIGN-ONLY → enforced (gac-local-gate + ci_gate)
- Historical violations cleanup is a separate task (migration, not this bet)
- Consider adding E-DOC rules to pre-commit hook for faster feedback
