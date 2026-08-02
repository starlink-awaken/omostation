<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# bin/

## Purpose
`bin/` is the workspace **operations and tooling directory** — a collection of Python and shell scripts that power the eCOS v6 governance, delivery, observability, and SSOT infrastructure. These are the executable engines behind agent workflows, health monitoring, governance gates, ADR management, and delivery pipelines. All scripts run via `uv run --with "pyyaml" python` or `bash`.

## Key Files
| File | Description |
|------|-------------|
| `agent-workflow.py` | Agent workflow lifecycle — bootstrap, start, claim, verify, closeout, compliance |
| `compass_radar.py` | Health score computation (ISC-3 composite formula: governance + freshness + runtime) |
| `ssot-guardian.py` | SSOT consistency guardian — validates state files against ground truth |
| `ssot-lint.py` | Doc-SSOT lint — ensures docs don't hard-code runtime facts |
| `adr/` | ADR management library (`_lib.py`: list, create, renumber, duplicate detection) |
| `gac/` | GaC governance toolkit — local gate, worktree guard, MOF validate |
| `delivery/` | Delivery automation — X3 auto-distribute, G-DEL metrics |
| `decks/` | Governance decks — port governance, capability drift |
| `agent-workflow.py` | Central workflow orchestrator for all agent operations |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `gac/` | Governance gate scripts (gac-local-gate, gac-worktree, gac-kos-sync) |
| `ssot/` | SSOT validation and generation (doc-ssot-lint, yaml-validate, check-hardcoded-ports) |
| `adr/` | ADR management utilities |
| `delivery/` | Delivery pipeline automation |
| `decks/` | Governance analysis decks |

## For AI Agents

### Working In This Directory
- All Python scripts use `uv run --with "pyyaml" python "bin/script.py"` execution model
- `agent-workflow.py` is the primary entry point for all agent operations
- `compass_radar.py` computes the health_score stored in `.omo/state/health.yaml`
- GaC scripts enforce governance rules. Don't bypass them without SWARM_ESCAPE_ID
- SSOT tools validate consistency between docs and runtime state

### Testing Requirements
```bash
# Run workspace tests that validate bin/ scripts
python -m pytest tests/ -v -k "agent_workflow or governance or ssot"

# Validate a specific script
uv run --with "pyyaml" python "bin/agent-workflow.py" doctor
```

### Common Patterns
- Scripts accept `--json` flag for machine-readable output
- Most scripts use `argparse` with subcommands
- SSOT validation scripts exit non-zero on violation
- Agent workflow scripts emit events to `.omo/_delivery/agent-workflows/events.jsonl`

## Dependencies

### Internal
- `.omo/state/system.yaml` — runtime state consumed by compass_radar
- `.omo/_truth/registry/agent-workflows.yaml` — workflow registry
- `protocols/port-registry.yaml` — port governance baseline
- `tests/` — test suite validating these scripts

### External
- `pyyaml` — YAML parsing (via uv --with)
- `pytest` — test framework
- `argparse` — CLI argument parsing

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
