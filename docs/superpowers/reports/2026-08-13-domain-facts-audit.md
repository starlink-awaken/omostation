---
type: ssot
last_updated: 2026-09-04
last-reviewed: 2026-08-26
owner: governance-team
---

# Documents Domain Facts Audit — 2026-08-13

## Scope

This report records Task 3's focused contract checks, scoped static checks, and
the live all-domain `facts-audit --json` read. The live command was read-only
against `/Users/xiamingxing/Documents`. No Documents, Runtime, manifest/
registry, client configuration, schedule, or legacy script was changed.

## Verification evidence

### Focused contracts

Exact invocation:

```bash
PYTHONPATH="src:/Users/xiamingxing/.local/share/omostation/accepted/projects/l4-kernel/src" uv run --no-project --with pytest --with pyyaml --with rich --with fastmcp --with fastapi python -m pytest src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py -q
```

Observed on 2026-08-13 07:24 +0800: `56 passed in 10.72s`; actual exit code
`0`. Captured artifact: `.omo/evidence/task-3-domain-facts-audit/focused.txt`.

### Scoped Ruff checks

Exact `ruff check` invocation from the brief exited `0` with `All checks
passed!`. Captured artifact: `.omo/evidence/task-3-domain-facts-audit/ruff-check.txt`.

Exact `ruff format --check` invocation from the brief exited `1`. Ruff reported
that `src/cockpit/commands/l4bridge.py:120:23` and
`src/cockpit/tests/test_governance_context_adapter.py:431:12` would be
reformatted; six files were already formatted. Captured artifact:
`.omo/evidence/task-3-domain-facts-audit/ruff-format-check.txt`.

After those two files were formatted by the parallel implementation work, the
same exact invocation was rerun and exited `0` with `8 files already formatted`.
The rerun output is captured at
`.omo/evidence/task-3-domain-facts-audit/ruff-format-rerun.txt`. Task 3 did not
edit or stage those source files.

### Live all-domain read

Exact invocation:

```bash
L4_DOCUMENTS_ROOT="/Users/xiamingxing/Documents" PYTHONPATH="src:/Users/xiamingxing/.local/share/omostation/accepted/projects/l4-kernel/src" uv run --no-project --with pyyaml --with rich --with fastmcp --with fastapi python -m cockpit.cli facts-audit --json
```

Observed envelope (actual exit code `1`):

| Field | Value |
| --- | --- |
| `schema` | `cockpit.domain-facts-audit.v1` |
| `status` | `violations` |
| `available` | `true` |
| `requested_domain_id` | `""` (all domains) |
| `total` | `12` |
| `summary` | `present=9`, `missing=3`, `unreadable=0`, `invalid=0` |

Complete JSON stdout is captured at `.omo/evidence/task-3-domain-facts-audit/cli-live-json.txt`; the standalone exit code is captured at `.omo/evidence/task-3-domain-facts-audit/cli-live-exit-code.txt`.

The `violations` result reports the current Documents facts state only. It is
not an instruction or authorization to mutate Documents, and no repair or
write was attempted. This evidence does not claim client installation or old
script migration.

## Boundary note

Only this report is intended for the Task 3 evidence commit. The full command
outputs remain under `.omo/evidence/` for auditability.
