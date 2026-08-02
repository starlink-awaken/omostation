<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# kos/

## Purpose
`kos/` is the **Knowledge Operating System (KOS) data directory**. It houses the KOS SQLite full-text search index and the manifest configuration that defines how the knowledge graph is indexed, what file patterns are scanned, and what entity extraction rules apply. KOS powers the `mcp-server-kos` MCP server, which provides semantic and full-text search across the entire workspace.

## Key Files
| File | Description |
|------|-------------|
| `kos-index.sqlite` | KOS search index — full-text and semantic index of workspace documents (*.py, *.md, *.txt, *.toml, *.yaml, *.json). Managed by the KOS daemon. |
| `manifest.json` | KOS manifest — defines zones (workspace scope), file patterns, indexing strategies, entity sources, and Chinese predicate patterns for relationship extraction |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| *(none — flat structure)* | |

## For AI Agents

### Working In This Directory
- **The SQLite index is managed by the KOS daemon.** Do not write to it directly.
- The `manifest.json` defines the workspace zone configuration including file patterns and Chinese-language relationship extraction patterns.
- To query the KOS index, use the `mcp-server-kos` MCP tools (`query_custom_sql`, `search_kos`, `list_entities`), not direct SQLite access.
- The index is rebuilt/updated by the KOS daemon on a schedule or on-demand.

### Testing Requirements
```bash
# KOS-specific tests
uv run --with "pyyaml" python "bin/ssot/test-mcp-kos.py"
```

### Common Patterns
- KOS manifest follows the schema: `{name, zones, entitySources, predicatePatterns, artifacts}`
- The SQLite index is at the path specified in `manifest.json → artifacts.retrievalDatabase`

## Dependencies

### Internal
- `bin/gac/gac-kos-sync.py` — KOS synchronization with governance checks
- `bin/gac/mcp-server-kos.py` — the KOS MCP server that serves queries against this index

### External
- SQLite 3 — embedded search index
- `mcp-server-kos` — MCP protocol server

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
