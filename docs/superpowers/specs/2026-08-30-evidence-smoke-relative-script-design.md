---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-30
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-75
risk_level: L1
---

# Evidence smoke relative-script resolution

## Decision

`bin/gac/evidence-smoke.py` must resolve a direct script argument relative to
the declared `--directory` when that option is present. The command contract
already uses this convention: `uv run --directory projects/omlxc python
examples/<script>.py` executes the script from the project directory. The
checker must inspect the same path without changing the service declaration.

## Scope

- Change only the stdio declaration resolver and its focused regression tests.
- Preserve root-relative behavior for commands without `--directory`.
- Preserve absolute paths and existing `--package`/`-m` resolution.
- Do not change BOS URIs, service commands, transport, runtime behavior,
  Documents content, or generated state.

## Acceptance criteria

1. A relative script with `--directory` resolves below that directory.
2. A missing relative script still fails closed.
3. A root-relative direct script without `--directory` keeps its current
   behavior.
4. The five OMLXC declarations resolve against the existing `projects/omlxc`
   example files without modifying their commands.
5. Focused tests pass and no new script-path gap is reported by the checker.

## Evidence boundary

The real service command remains the execution authority. The checker only
validates declaration reachability; it must not spawn or execute a service in
the L2 path.
