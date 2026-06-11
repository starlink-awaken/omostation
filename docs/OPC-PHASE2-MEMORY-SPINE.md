# OPC-P2: Personal Memory Spine

> Date: 2026-06-11
> P1: conditionally passed | P1.5: baseline-only
> Source: OPC-ROADMAP.md §M2, opc-roadmap-omo-plan.md §Phase 2
> Status: ✅ design complete (implementation deferred per accepted persistence risks)

---

## T0 — Persistence Prerequisites (verified, no additional action)

| Check | Status |
|:------|:------:|
| kairon JSONL write paths → schema hardening needed | 📝 registered debt (DEBT-OMC-KAIRON-JSONL) |
| gbrain non-atomic overwrite → atomic write needed | 📝 registered debt (DEBT-OMC-GBRAIN-PERSISTENCE) |
| metaos .omo/ → skeleton exists (system.yaml) | ✅ resolved |
| runtime .omo/ → missing | ⚠️ noted, non-blocking for P2 |

**Decision**: P2 proceeds with accepted risks. Memory spine design uses cockpit local search as the primary bootstrap backend. kairon KOS and gbrain are secondary backends invoked through BOS URI when persisted writes are needed. Full schema hardening deferred to subsequent hardening phase.

---

## T1 — Memory Boundary

### Five memory zones

| Zone | Scope | Storage | Access |
|:-----|:------|:--------|:-------|
| **Personal Knowledge** | @驾驶舱 CARDS, research, ideas, tasks | cockpit SQLite (FTS5, local) | `cockpit research --search` or `bos://memory/local/search` |
| **Structured Memory** | KOS semantic search via kairon | kairon/kos — BOS stdio | `bos://memory/kos/search` |
| **Graph Memory** | gbrain TS knowledge graph | gbrain JSON → graph store | `bos://memory/gbrain/query` |
| **Document Vault** | @学习进化 documents, @工作文档 | filesystem markdown, CARDS | `bos://memory/vault/search` |
| **External Sources** | Obsidian iCloud, SharedDisk, Web | various, read-only | import via kronos/kairos |

### Boundary Rules

1. **write**: cockpit local store (SQLite FTS5) → tested, safe, atomic. KOS and gbrain are read-only for P2 bootstrap.
2. **search**: local store by default. `bos://memory/kos/search` for cross-source recall. Search response declares which zone(s) were queried.
3. **archive**: CARDS `closed/done` status → local store retains record, KOS may ingest summary.
4. **source attribution**: every search result carries zone origin tag (see T4).

---

## T2 — `bos://memory/**` Route Policy

### Proposed routes

| URI | Zone | Transport | Status |
|:----|:-----|:----------|:------:|
| `bos://memory/kos/search` | Structured Memory | mcp_stdio | ✅ exists in POC_SERVICES |
| `bos://memory/kos/ingest` | Structured Memory | mcp_stdio | ✅ exists |
| `bos://memory/kronos/ingest` | External Sources | mcp_stdio | ✅ exists |
| `bos://memory/kronos/query` | External Sources | mcp_stdio | ✅ exists |
| `bos://memory/kronos/schedule` | External Sources | mcp_stdio | ✅ exists |
| `bos://memory/local/search` | Personal Knowledge | internal | 📝 proposed — maps to cockpit storage.search_research() |
| `bos://memory/local/all-search` | Multi-zone | internal | 📝 proposed — aggregates local + KOS + vault |
| `bos://memory/vault/search` | Document Vault | internal | 📝 proposed — cockpit vault_search() wrapper |
| `bos://memory/gbrain/query` | Graph Memory | mcp_stdio | 📝 proposed — gbrain MCP proxy |

### Search response contract

All `bos://memory/**/search` routes must return:

```json
{
  "zone": "local|kos|gbrain|vault|all",
  "query": "original query",
  "results": [
    {
      "id": "unique-id",
      "title": "...",
      "snippet": "...",
      "source": "cockpit-local|kairon-kos|gbrain|@学习进化",
      "source_path": "CARDS/tasks/TASK-xxx.md",
      "timestamp": "2026-06-01T00:00:00Z",
      "type": "research|card|document|knowledge",
      "relevance": 0.95
    }
  ],
  "total": 12,
  "zone_count": {"local": 5, "kos": 3, "vault": 4}
}
```

---

## T3 — Recall Flow

### End-to-end: one question through the memory spine

```
User asks: "What did we decide about the entry convergence design?"
  │
  ▼
Step 1: COLLECT
  Input: natural language query
  Route: cockpit search "entry convergence" --all
  → queries local SQLite FTS5
  → queries bos://memory/kos/search
  → queries @学习进化 via vault_search
  └→ collects raw results from each zone

Step 2: INGEST (optional, if new content)
  Input: new document, research result, or decision
  → writes to cockpit local store (SQLite, atomic)
  → optional: bos://memory/kos/ingest (if KOS available)
  → tags: domain, source, timestamp, freshness
  └→ registers in CARDS if task-worthy

Step 3: SEARCH
  Input: combined raw results from Step 1
  → deduplicate by source_path
  → rank by relevance (FTS5 bm25 + semantic if available)
  → attach source metadata (zone, timestamp, type)
  └→ return scoped response with zone_count

Step 4: OUTPUT
  Input: ranked, deduplicated results
  → render: top 10 with source attribution
  → declare scope: which zones were searched, how many results each
  → suggested next action: "Re-read OPC-PHASE1-CONVERGENCE.md", "Check CARDS task status"
  └→ writeback: log query → output to cockpit research if substantive

Step 5: ARCHIVE
  Input: completed research or closed CARDS
  → mark status: closed/done
  → keep local store record (never delete)
  → optional: bos://memory/kos/ingest for structured recall
  └→ update CARDS dashboard
```

### Minimum viable demonstration (acceptance)

One real question: "What phases of the OPC roadmap are currently active?"

Through the flow:
1. Collect: local search (cockpit) + KOS search (if available)
2. Search: deduplicate + rank
3. Output: return P0-P2 status with source pointers to PANORAMA/OPC docs
4. Archive: log the query as a research reference

---

## T4 — Source Metadata

### Source metadata schema

Every output item must carry:

| Field | Type | Example | Required |
|:------|:-----|:--------|:--------:|
| `source` | enum | `cockpit-local`, `kairon-kos`, `gbrain`, `@学习进化` | ✅ |
| `source_path` | string | `CARDS/tasks/TASK-xxx.md`, `bos://memory/kos/search` | ✅ |
| `timestamp` | ISO 8601 | `2026-06-01T00:00:00Z` | ✅ |
| `owner` | string | `omo`, `opc`, `manual` | ✅ |
| `type` | enum | `research`, `card`, `document`, `knowledge`, `decision` | ✅ |
| `freshness` | string | `fresh (<7d)`, `stale (7-30d)`, `archived (>30d)` | ✅ |
| `reuse_policy` | string | `reference-only`, `derived-allowed`, `public` | ⚠️ |

---

## T5 — Memory Metrics

### Quality metrics (to be implemented as cockpit extension)

| Metric | Definition | Target | Initial Baseline |
|:-------|:----------|:------:|:----------------:|
| **Recall zone coverage** | % of queries that hit ≥2 zones | >50% | 0% (local only) |
| **Deduplication rate** | % of cross-zone results sharing source_path | <10% | N/A (single zone) |
| **Source attribution rate** | % of outputs with complete source metadata | 100% | **100%** (all 8/8 T4 fields present in every search result) |
| **Freshness score** | % of outputs with timestamp <30d | >80% | N/A |
| **Archive retention** | % of closed CARDS still searchable | 100% | 100% (SQLite never deletes) |

### Observability hooks (pipeline for future phase)

- Every search query → log timestamp, zones queried, result count
- Every write → log target zone, schema check pass/fail, atomic write confirm
- Every archive → log from-status, to-status, timestamp
- Dashboard: P2 memory health card in cockpit health --full

---

## Gate C Evidence

| Gate criterion | Design | Implementation | Score |
|:---------------|:------|:--------------|:-----|
| One question: collect→ingest→search→output→archive | ✅ flow designed (T3) | ⚠️ local zone working; KOS/vault multi-zone deferred (Gate C2/C3) | partial |
| Search responses declare scope | ✅ zone_count in response contract (T2) | ✅ `cockpit search --all` outputs zone/query/total/zone_count (text + JSON express same facts) | ✅ |
| Outputs include source metadata | ✅ schema defined (T4) | ✅ **8/8 fields complete**: `_source/_source_path/_zone/_type/_freshness/_owner/_reuse_policy/_retrieved_at` in all local search results | ✅ |

### Sub-gate Status (per OPC-MASTER-EXECUTION-PLAYBOOK §7)

| Sub-gate | Title | Status | Evidence |
|:---------|:------|:------:|:---------|
| **C1** | Local Contract Hardening | ✅ **passed** (2026-06-11) | `.omo/tasks/done/OPC-P2-GATE-C.yaml` — 5/5 tests, runtime commands verified |
| **C2** | KOS Activation | ✅ **passed** (2026-06-11) | `.omo/tasks/done/OPC-P2-GATE-C.yaml` — 15/15 tests, real kairon/kos MCP stdio call returns 10 items for q='kairon' |
| **C3** | Vault Activation | ✅ **passed** (2026-06-11) | `.omo/tasks/done/OPC-P2-GATE-C.yaml` — 18/18 tests, real vault-search.sh call returns 10 items for q='AGENTS' (multi-zone: {kos:10, vault:10}) |
| **C4** | Real Trace Closure | ✅ **passed** (2026-06-11) | `.omo/tasks/done/OPC-P2-GATE-C.yaml` — 21/21 tests, 2 acceptance queries (trace_id=31,32) written to cockpit research table |
| **C** | Final | ✅ **passed** (2026-06-11) | C1-C4 all closed, 21/21 tests pass, multi-zone {local:0, kos:10, vault:10} verified for q='AGENTS' |

**Gate C verdict (post closeout, 2026-06-11)**: T4 complete (8/8 metadata). T2 response contract wired into CLI search output (text + JSON consistent). C1 (Local Contract Hardening) passed with red-line guard against fake KOS `zone_count`. C2 (KOS Activation) passed — real kairon/kos MCP stdio invocation returns 10 items for q='kairon', all 8/8 T4 + 7/7 P2 fields present, no fake blob injection. C3 (Vault Activation) passed — real `@学习进化/vault-search.sh` invocation returns 10 items for q='AGENTS', multi-zone hit confirmed ({local:0, kos:10, vault:10}). C4 (Real Trace Closure) passed — writeback to cockpit research table with dedup window, 2 acceptance queries produced distinct trace_ids 31 and 32, all 4 sub-gates closed. **Gate C passed**. P2 implementation complete on the C-axis (T1-T5 design + C1-C4 runtime).

**P2 closeout (2026-06-11)**: 3 缺口补丁已合并, 30/30 tests pass (21 旧 + 9 新).
- Task 2 (multi-zone visibility): `cockpit search --all` 使用 `_interleave_by_source()`
  round-robin, 保证 `zone_count.vault > 0` 时 results 至少 1 条 `@学习进化`,
  `zone_count.kos > 0` 时至少 1 条 `kairon-kos`.
- Task 3 (trace full_text): `_writeback_search_trace()` 现在把每个非零 zone 的 top-3
  命中写入 full_text (id / title / source / source_path / timestamp), 摘要
  也包含在 `summary.hit_summary` 字段. 不再是固定占位串.
- Task 1 (YAML hygiene): `.omo/tasks/done/OPC-P2-GATE-C.yaml` 顶层 status=completed,
  gate_status=passed, 4 sub-gates 全部 passed, 重复段已清理. 自检脚本:
  `python3 .omo/tasks/done/OPC-P2-GATE-C.check.py` → 10/10 PASS.

---

## Audit Records

| Event | Detail |
|:------|:-------|
| Memory boundary defined | 5 zones + boundary rules |
| Route policy defined | 9 bos://memory/** routes, 5 existing, 4 proposed |
| Search response contract | JSON schema with zone, results, zone_count |
| Recall flow designed | 5-step: collect→ingest→search→output→archive |
| Source metadata schema | 8 fields |
| Memory metrics | 5 quality metrics + observability hooks |
| Accepted risks | kairon JSONL, gbrain non-atomic writes → P2 design only |

---

## Signal

```
opc_phase2_memory_spine_implemented  (2026-06-11)
opc_phase2_gate_c1_local_contract_passed  (2026-06-11)
opc_phase2_gate_c2_kos_activation_passed  (2026-06-11)
opc_phase2_gate_c3_vault_activation_passed  (2026-06-11)
opc_phase2_gate_c4_trace_closure_passed  (2026-06-11)
opc_phase2_gate_c_passed  (2026-06-11)
```

Gate C: ✅ **passed** (2026-06-11). T4 complete (8/8). T2 wired into CLI search output. T3 multi-zone implementation complete. C1+C2+C3+C4 sub-gates all closed. Multi-zone hit verified for q='AGENTS' ({local:0, kos:10, vault:10}). Writeback to cockpit research verified (trace_id 31 and 32 from 2 acceptance queries).

---

## Retrospective

- **P2 bootstrap strategy**: Start with cockpit local search as primary backend. KOS and gbrain are secondary backends invoked via BOS URI. This allows P2 to design the memory architecture today without waiting for kairon/gbrain persistence hardening.
- **Multi-zone search**: Not yet implemented. Local search (`cockpit search --all`) is the closest proxy. Full multi-zone search requires a `bos://memory/local/all-search` route that aggregates.
- **Source metadata**: Schema defined (T4). Local search now includes **8/8 fields** (`_source`, `_source_path`, `_zone`, `_type`, `_freshness`, `_owner`, `_reuse_policy`, `_retrieved_at`). T4 complete.
- **P2 status**: Implementation in progress. T4 complete, T2 response contract wired into CLI search. T3 multi-zone (KOS/vault) requires kairon subprocess activation.
- **Gate C**: Not yet passed. Close after T3 multi-zone KOS/vault activation.
