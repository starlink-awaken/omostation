<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# protocols/

## Purpose
`protocols/` is the workspace **protocol and contract registry** — a collection of read-only SSOT (Single Source of Truth) YAML files that define system-wide contracts: port allocation, vault path mapping, and axis registries. These files are the authoritative configuration that all projects and tools must respect. They are the L0/M0 layer of the eCOS architecture, establishing the foundational contracts that prevent drift and conflict across the workspace.

## Key Files
| File | Description |
|------|-------------|
| `port-registry.yaml` | **SSOT**: Port allocation registry — every TCP/UDP port, stdio channel, and transport endpoint in the workspace. Fields: name, transport (stdio/http/sse/udp/deprecated), status (active/deprecated/reserved) |
| `vault-paths.yaml` | **SSOT**: Vault path mapping — canonical paths for all vault/storage locations. Eliminates hard-coded `~/Documents/` paths across the workspace |
| `x-axis-registry.yaml` | **SSOT**: X-axis governance registry — defines the X1-X4 governance axis contracts and their validation rules |
| `port-hardcode-baseline.yaml` | Baseline snapshot of historical hardcoded ports — used by lint tools to detect new violations |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| *(none — flat structure)* | |

## For AI Agents

### Working In This Directory
- **READ-ONLY for agents.** These files are SSOT contracts. Do not modify them casually.
- Port allocation: always check `port-registry.yaml` before assigning a new port.
- Vault paths: reference `protocols/vault-paths.yaml` instead of hard-coding any path.
- Changes to these files require ADR approval and must be validated by `bin/ssot/` tooling.

### Testing Requirements
```bash
# Validate no new hardcoded ports
uv run --with "pyyaml" python "bin/ssot/check-hardcoded-ports.py"

# Validate YAML syntax
uv run --with "pyyaml" python "bin/ssot/yaml-validate.py" protocols/
```

### Common Patterns
- Port registry entries: `{port}: name, transport, status, note`
- Vault path entries: `{key}: {absolute_path}`
- All YAML files use 2-space indentation and UTF-8 encoding.

## Dependencies

### Internal
- `bin/ssot/check-hardcoded-ports.py` — enforces port registry compliance
- `bin/ssot/yaml-validate.py` — syntax validation
- `bin/gac/gac-mof-validate.py` — cross-validates MOF/L0 alignment

### External
- `pyyaml` — YAML parsing

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
