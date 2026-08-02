<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# data/

## Purpose
`data/` is the workspace **runtime data substrate** — persistent but non-source data that supports the operational lifecycle. This includes KOS search indices, shared brain data, cockpit document stores, and provider plane caches. This directory contains data that is too large or too dynamic for git tracking, but is essential for runtime operation.

## Key Files
| File | Description |
|------|-------------|
| `kos/` | KOS knowledge index data (SQLite + manifest) — symlinked from `kos/` |
| `sharedbrain/` | SharedBrain data store — legacy knowledge graph data |
| `驾驶舱/documents.db` | Cockpit document database (gitignored) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `kos/` | KOS search index artifacts (see `kos/AGENTS.md`) |
| `sharedbrain/` | Legacy brain data (being migrated to KOS) |
| `驾驶舱/` | Cockpit-specific data stores |

## For AI Agents

### Working In This Directory
- **This is data, not source.** Do not commit changes from this directory.
- Most contents are gitignored. Check `.gitignore` section 4 for details.
- KOS data is managed by the KOS daemon — use `mcp-server-kos` tools to query, not direct file access.
- `驾驶舱/documents.db` is a SQLite database used by the cockpit service.

### Testing Requirements
```bash
# No direct tests for data/ contents
# KOS tests: uv run --with "pyyaml" python "bin/ssot/test-mcp-kos.py"
```

### Common Patterns
- Data files are named with timestamps or content hashes for cache-busting
- SQLite databases use WAL mode for concurrent access
- Large binary files are gitignored and re-fetched on demand

## Dependencies

### Internal
- `kos/` — KOS search index (symlink or colocated)
- `bin/gac/gac-kos-sync.py` — KOS synchronization with governance
- `projects/cockpit/` — cockpit service that reads documents.db

### External
- SQLite 3 — embedded database
- KOS daemon — index management

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
