---
type: ssot
owner: governance-team
last_updated: 2026-09-04
---

# CLAUDE.md — AI Context Loader

> Session startup protocol. Operating rules: [AGENTS.md](AGENTS.md). Architecture: [ARCHITECTURE.md](ARCHITECTURE.md).

## 0. This Repo

**omostation** — root workspace for **eCOS v6**: knowledge engineering + agent governance + BOS routing + runtime orchestration.

- **Shape**: Polyglot monorepo, sub-projects under `projects/*` (independent git submodules)
- **Architecture**: `5+4+1+1` layering (L0 protocol → L4 self + I0 weave + M0 crosscut + X extension)
- **Governance**: X1-X4 axes + DFSQ/SFOP slots + BOS URI routing
- **Document SSOT**: Each doc owns one dimension — see [ARCHITECTURE.md §1](ARCHITECTURE.md)

> **Navigation hub**: [docs/SYSTEM-INDEX.md](docs/SYSTEM-INDEX.md) — find projects, tools, ADRs, skills.

## 1. Startup Protocol

### Step A — Situational Load (first turn / realign)

```bash
mcp-server-kos::query_custom_sql(sql="SELECT doc_id, title, canonical_path FROM documents WHERE canonical_path LIKE '%BRIEF.md%' LIMIT 1")
mcp-server-kos::search_kos(query="ADR-012")
mcp-server-kos::list_entities(limit=50)
```

### Step B — Workflow Load (every session)

```bash
make agent-workflow-bootstrap
make agent-workflow-status
make omo-status        # <0.2s Rich snapshot
```

### Architecture Constraints Check

1. Scene card lifecycle: draft→shadow→assisted→supervised→routine (ordered)
2. Business domain: each scene card needs `domain` field
3. Script quota: add 1 bin script = delete 1 (invariant)

## 2. Session Role

This file answers: what to read first, which files are authoritative, which operations need broker/approval.

**Does not duplicate**: project tables, architecture diagrams, rule registries, test counts, port values.

## 3. Mandatory Boundaries

Authoritative SSOT map (fact types → sources): [ARCHITECTURE.md §1](ARCHITECTURE.md)

## 4. Working Discipline

1. Keep a visible todo list for multi-step work
2. Use `rg` for text discovery; codebase-memory MCP for callers/impact
3. Use file-editing tools (Edit, Create, MultiEdit, apply_patch) for manual edits
4. If governance demands commit but policy doesn't authorize, finish changes + report files + ask for confirmation

## 5. Routing Hints

| Need | Route |
|------|-------|
| Projects by layer | [docs/SYSTEM-INDEX.md](docs/SYSTEM-INDEX.md) |
| Tools & scripts | [bin/README.md](bin/README.md) |
| ADRs, audits, patterns | [.omo/_knowledge/](.omo/_knowledge/) |
| Agent skills | [.agents/skills/](.agents/skills/) |
| Scene cards & journeys | [docs/superpowers/](docs/superpowers/) |

## 5. Closeout

```bash
git status --short
make gac-local-gate
make ssot-guardian
```

Full checklist: [AGENTS.md §9](AGENTS.md)

---

> **Pyramid principle**: Navigation layer only. All operational details live in AGENTS.md or dedicated docs.

## 6. Onboarding & Patterns

New agent? Read these historical patterns to avoid known pitfalls:
- [P74 Workflow Solidification](.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md)
- [P73 Truth-Driven Engineering](.omo/_knowledge/patterns/p73-truth-driven-engineering-pattern.md)

Anti-corrosion framework: [.omo/_knowledge/decisions/0431-anti-corrosion-five-layer-framework.md](.omo/_knowledge/decisions/0431-anti-corrosion-five-layer-framework.md)
