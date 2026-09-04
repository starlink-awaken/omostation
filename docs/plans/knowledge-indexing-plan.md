---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
type: ephemeral
---

# Knowledge Indexing Plan — #7 from Architectural Review

> **Author**: deep analysis session, 2026-08-24
> **Status**: PLANNING — not yet implemented
> **Estimated effort**: 2-4 weeks phased
> **Prerequisites**: drift-sweep 16/16 PASS (done), validate-runbook-refs (done)

---

## 1. Current State Assessment

### What exists today

| Asset | Count | Indexed? | Generator |
|---|---|---|---|
| docs/*.md | 342 | ❌ | — |
| bin/ scripts (.py/.sh) | 472 | ✅ | gen-tools-index.py → INDEX-TOOLS.md |
| ADRs (.omo/_knowledge/decisions/) | 382 | ✅ | gen-knowledge-index.py → INDEX-KNOWLEDGE.md |
| .omo/_knowledge/**/*.md | 1843 | ❌ | — |
| Skills (.agents/skills/) | 27 | ❌ | — |
| Runbooks (docs/operations/) | 7+85 | ❌ | manual |
| Scene cards (docs/scene-cards/) | 9 | ❌ | — |
| Protocols (protocols/*.yaml) | 5 | ✅ | port-registry etc |

### Gaps

1. **No cross-referencing** — an operator looking at ADR-0412 has no way to find:
   - The scripts it created or modified
   - The runbook that explains how to operate those scripts
   - Other ADRs that reference or supersede it
   - The scene cards that depend on it

2. **No keyword search** — `grep -r "drift"` returns 200+ matches across 5 directories with no ranking or context.

3. **No freshness signal** — a doc last reviewed in June may reference a script renamed in August.

4. **No dependency graph** — when `bin/gac/gac-drift.py` is renamed, nothing tells you which ADRs, runbooks, and skills reference it (validate-runbook-refs only covers runbooks).

---

## 2. Design: Three Phases

### Phase 1: Knowledge Graph Bootstrap (Week 1)

Build `bin/kb/knowledge-graph.py` that scans all assets and produces a machine-readable index:

```
.kb/graph.json
{
  "generated_at": "...",
  "nodes": [
    {"type": "adr", "id": "ADR-0412", "path": ".omo/_knowledge/decisions/0412-....md", "title": "...", "status": "active"},
    {"type": "script", "path": "bin/gac/drift-sweep.py", "name": "drift-sweep", "category": "gac"},
    {"type": "runbook", "path": "docs/operations/runbook-ci-red.md", "title": "..."},
    {"type": "skill", "path": ".agents/skills/ci-red-triage/SKILL.md", "name": "ci-red-triage"},
    {"type": "scene-card", "path": "docs/scene-cards/engineering-delivery-dogfood.yaml", "scene_id": "..."},
    {"type": "doc", "path": "docs/operations/README.md", "title": "..."}
  ],
  "edges": [
    {"from": "runbook:ci-red", "to": "script:gac-local-gate", "relation": "references"},
    {"from": "adr:0412", "to": "script:sync-planned-to-done", "relation": "created"},
    {"from": "skill:ci-red-triage", "to": "runbook:ci-red", "relation": "complements"}
  ]
}
```

**Extraction methods per node type**:
- **ADR**: parse frontmatter (`status`, `lifecycle`, `title`) + regex for `bin/` refs
- **Script**: parse docstring first line + grep for `--json` flag (is it gate-wired?)
- **Runbook**: parse frontmatter + extract `bin/` refs via validate-runbook-refs logic
- **Skill**: parse SKILL.md frontmatter + extract `bin/` refs
- **Scene card**: parse YAML frontmatter (`scene_id`, `journey_id`, `owner`)
- **Doc**: parse title from first heading

**Edge extraction**:
- Doc references script: grep for `bin/X.py` pattern
- ADR references another ADR: grep for `ADR-\d+` pattern  
- Skill complements runbook: name similarity (e.g. `ci-red-triage` ↔ `runbook-ci-red`)
- Script owned by check: grep governance-checks.yaml for script path

### Phase 2: Search Interface (Week 2)

Build `bin/kb/search.py`:

```bash
# Search by keyword
bin/kb/search.py "drift"
→ ranked results from graph.json nodes + edges matching keyword

# Search by type
bin/kb/search.py --type adr "concurrent write"

# Find references to a specific script
bin/kb/search.py --refs bin/gac/drift-sweep.py
→ lists every ADR, runbook, skill, and doc that mentions it
```

Implementation: simple inverted index over node titles + edge relations.
No external dependencies (no SQLite, no vector DB). Pure Python dict.

### Phase 3: Freshness & Staleness Detection (Weeks 3-4)

Build `bin/kb/staleness-check.py`:

For each knowledge asset, compute staleness score based on:
1. **mtime age** — when was the file last touched?
2. **Reference validity** — do all `bin/` refs still exist?
3. **Frontmatter `last-reviewed`** — is it within 90 days?
4. **Code-doc divergence** — does the script's `--help` output match what the doc says?

Output: `.kb/staleness.json` with per-asset scores and a summary.

Wire into drift-sweep.py as a new check: `knowledge_staleness`.

---

## 3. File Structure

```
bin/kb/
  __init__.py
  knowledge-graph.py    # Phase 1: build .kb/graph.json
  search.py             # Phase 2: query interface
  staleness-check.py    # Phase 3: freshness detection
  README.md             # usage guide

.kb/                    # gitignored (generated)
  graph.json
  staleness.json
```

## 4. Integration Points

| Surface | Change |
|---|---|
| `make kb-build` | runs knowledge-graph.py, outputs .kb/graph.json |
| `make kb-search Q="..."` | runs search.py with query |
| `make kb-staleness` | runs staleness-check.py |
| `drift-sweep.py` | adds `knowledge_staleness` check |
| `docs/operations/README.md` | adds KB section to Tool Reference |
| CI (weekly cron) | runs kb-build + staleness, emits report |

## 5. Non-Goals (intentional)

- **No vector database** — overkill for 2700 assets; simple keyword search suffices
- **No LLM-powered summarization** — the system already has enough moving parts
- **No web UI** — terminal-native is the project's philosophy
- **No real-time indexing** — batch rebuild on demand (`make kb-build`) is sufficient
- **No automatic doc generation from code** — docs should stay hand-written; the graph indexes them, not generates them

## 6. Risk Assessment

| Risk | Mitigation |
|---|---|
| graph.json grows too large | Cap at ~10k edges; prune archived paths |
| Regex extraction false positives | Same heuristic as validate-runbook-refs (skip examples/templates) |
| Concurrent agents rebuild simultaneously | Atomic write via tmp+rename (same as compass_radar) |
| Search results too noisy | Rank by: exact title match > edge relation > body mention |

## 7. Success Criteria

After Phase 1-3 are done, an operator should be able to:

```bash
# "What's related to concurrent-write handling?"
bin/kb/search.py "concurrent write"
→ 3 ADRs, 2 runbooks, 1 skill, 4 scripts

# "What references gac-drift.py?"
bin/kb/search.py --refs bin/gac/gac-drift.py
→ 2 ADRs, 1 skill, 1 governance-check rule

# "What's stale?"
bin/kb/staleness-check.py --summary
→ 12 docs older than 90d, 3 broken refs, 2 missing last-reviewed
```

And `drift-sweep.py` includes `knowledge_staleness` in its 16 checks.

---

## 8. Effort Estimate

| Phase | Scripts | Tests | Time |
|---|---|---|---|
| 1: Graph bootstrap | ~200 lines | ~15 cases | 3 days |
| 2: Search | ~100 lines | ~8 cases | 1 day |
| 3: Staleness | ~150 lines | ~10 cases | 3 days |
| Integration + docs | ~50 lines Makefile + README | — | 1 day |
| **Total** | **~500 lines** | **~33 cases** | **~8 working days** |

---

## 9. Decision Point

This is the largest remaining item from the architectural review. It requires
~8 working days of focused effort. Before starting, confirm:

1. Is there a more urgent priority? (e.g. user-facing features)
2. Should this be done by one agent or split across concurrent agents?
3. Should the output be committed to git or kept as runtime-only?

**Recommendation**: Do Phase 1 alone first (~3 days). If the graph proves useful,
continue to Phases 2-3. If not, we've lost only 3 days and gained a reusable
asset extractor.
