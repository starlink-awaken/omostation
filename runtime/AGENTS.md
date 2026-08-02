<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# runtime/

## Purpose
`runtime/` is the workspace home for **ephemeral runtime residue** — non-durable, execution-generated artifacts that support the workspace's operational lifecycle. This includes local logs, PID/socket files, session heartbeats, runtime boundary contracts, sandbox state, cron outputs, and agent session data. This directory is distinct from `projects/runtime/` (which is the runtime daemon codebase) — this top-level `runtime/` is purely for operational residue, not source code.

## Key Files
| File | Description |
|------|-------------|
| `system-runtime-boundary.yaml` | System-level runtime boundary contract — defines what is/isn't allowed in the runtime space |
| `runtime-space-boundary.yaml` | Runtime space boundary — access control for runtime artifacts |
| `.watch-dispatch-stamps.json` | Dispatch timestamp tracking for watch agents |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `logs/` | Local log files from daemon execution |
| `data/` | Temporary runtime data (caches, intermediate state) |
| `omo/` | Runtime OMO state residue (ephemeral, not the canonical `.omo/`) |
| `sandbox/` | Sandbox execution environments and their state |
| `cron/` | Cron job outputs and scheduling state |
| `agent-sessions/` | Agent session heartbeats and continuation markers |

## For AI Agents

### Working In This Directory
- **This is ephemeral state.** Do not commit changes from this directory. It is gitignored.
- Log files are the primary debugging resource for runtime issues. Check `logs/` first when diagnosing daemon failures.
- Boundary YAML files define the contract for what belongs in runtime space.
- Agent session data is managed by the agent runtime system. Don't manually edit session state.

### Testing Requirements
```bash
# Integration tests validate runtime behavior
bash "tests/integration/run-all.sh"
```

### Common Patterns
- Runtime artifacts are named with timestamps or session IDs for uniqueness.
- Boundary contracts follow YAML schema: `allowed_paths`, `denied_patterns`, `max_size`.

## Dependencies

### Internal
- `projects/runtime/` — the runtime daemon that produces most of these artifacts
- `bin/gac/gac-daemon.py` — governance daemon
- `agent-runtime/` — agent session management

### External
- No direct external dependencies at this level

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
