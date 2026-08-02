<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# tests/

## Purpose
`tests/` is the workspace-level **integration and end-to-end test suite**. It contains tests that validate cross-project contracts, governance tooling, agent workflows, SSOT consistency, and runtime behavior at the workspace level. Unlike project-level tests (which live inside each `projects/*/` repo), these tests validate the interactions between projects, the correctness of `bin/` scripts, and the integrity of the overall eCOS v6 system.

## Key Files
| File | Description |
|------|-------------|
| `test_agent_workflow.py` | Agent workflow lifecycle tests (bootstrap, start, claim, verify, closeout) |
| `test_governance_evolution.py` | Governance evolution and convergence tests |
| `test_swarm_discipline.py` | Swarm agent discipline and coordination tests |
| `test_doc_governance_check.py` | Documentation governance lint tests |
| `test_gac_coverage_lint.py` | GaC coverage lint validation tests |
| `test_registry_sync.py` | Registry synchronization tests |
| `test_requirement_iteration_gate.py` | Requirement iteration workflow gate tests |
| `test_phase_gate_check.py` | Phase gate validation tests |
| `test_cross_repo_consistency.py` | Cross-repository consistency validation |
| `test_hardcoded_ports.py` | Hardcoded port detection tests |
| `test_god_module_lint.py` | God module lint tests |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `integration/` | Integration test scripts — shell-based e2e, smoke tests, pipeline tests |
| `gac/` | GaC-specific test suite |

## For AI Agents

### Working In This Directory
- Tests are organized by the component they validate. Name tests `test_<feature>.py`.
- Integration tests in `tests/integration/` are shell scripts (`.sh`) and Python e2e tests.
- The canonical integration runner is `tests/integration/run-all.sh`.
- GaC tests validate governance gate correctness — critical, don't break them.

### Testing Requirements
```bash
# Run all workspace tests
python -m pytest tests/ -v

# Run a specific test
python -m pytest tests/test_agent_workflow.py -v

# Run integration suite
bash "tests/integration/run-all.sh"
```

### Common Patterns
- Tests use `uv run --with "pyyaml" python` or `python -m pytest` directly.
- Integration tests use `bash` with `set -euo pipefail` for fail-fast behavior.
- Tests that validate `bin/` scripts import from the script or invoke it as a subprocess.

## Dependencies

### Internal
- `bin/` — most tests validate scripts in this directory
- `protocols/` — port/vault tests reference registry files
- `.omo/` — some tests validate state files

### External
- `pytest` — Python test framework
- `pyyaml` — YAML parsing in tests

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
