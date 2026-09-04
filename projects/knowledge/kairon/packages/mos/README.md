---
title: README
type: doc
---

# mos — Memory OS control plane

Unified memory control plane for eCOS (ADR-0372, **phase10**):  
**write** / **recall** / **status** / **forget** / **consolidate** / **knowledge-ref**.

## Features

- Envelope validation + intent routing + dual-track (raw audit + theta searchable)
- Neo4j FACT write/recall when `NEO4J_URI` set; otherwise TemporalShadow
- **Bi-temporal `as_of`** on neo4j/temporal recall (ISO-8601; omit = current state)
- Optional **live KOS / gbrain** backends (`MOS_LIVE_KOS` / `MOS_LIVE_GBRAIN` / `MOS_LIVE_GBRAIN_WRITE`)
- RBAC via `.omo/_truth/registry/memory-rbac.yaml` (`MOS_RBAC=1`)
- FileStore continuity: theta/raw + `last_consolidate`

## Package tests

```bash
cd projects/kairon
uv run --package mos pytest packages/mos/tests -q
# or:
PYTHONPATH=packages/mos/src python3 -m pytest packages/mos/tests -q
```

## Workspace entry points (prefer over raw `python -m mos`)

| Surface | Call |
|---------|------|
| CLI | `cockpit memory {status,recall,write,forget,consolidate,knowledge-ref}` |
| Help | `cockpit memory` · `cockpit memory recall --help` |
| HTTP/UI | `/api/memory/*` · `/memory` |
| BOS / Agora MCP | `bos://memory/mos/{write,recall,status,forget,consolidate,knowledge-ref}` |

### Examples

```bash
source bin/memory-os-env.sh
bash bin/memory-os-neo4j-up.sh          # optional graph

cockpit memory status --json
cockpit memory recall "Alice" --intent temporal_fact --as-of 2021-06-01T00:00:00Z --json
cockpit memory write --type semantic --content "…" --subject A --predicate works_at --object B --json
cockpit memory consolidate --dry-run --json

# BOS
cockpit bos resolve bos://memory/mos/status
```

### Live backends (default **off**)

```bash
# config/memory-os.env
MOS_LIVE_KOS=1              # HTTP KOS_API_URL (default http://localhost:8766)
MOS_LIVE_GBRAIN=1           # bun + projects/gbrain search
MOS_LIVE_GBRAIN_WRITE=1     # best-effort gbrain put on write (optional)
```

When flags are off or backends unavailable, FileStore fixtures remain; `status.adapters` reports honesty.

## Env / ops

- Bootstrap: `source bin/memory-os-env.sh` · template `docs/operations/memory-os.env.example`
- Ops contract: `.omo/standards/memory-os-ops.md`
- Architecture: `docs/architecture/memory-os.md`
- Registry: `.omo/_truth/registry/memory-os.yaml`
- Skill: `.agents/skills/memory-recall/SKILL.md`
- Check: `make memory-os-check`
