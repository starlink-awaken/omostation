---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Operation Levels Rollout Plan

> 状态: merged
> 已合并至 `.omo/standards/operation-levels.md`
> 本文件保留为历史 rollout 细节来源，不再作为新的 workflow 引用入口。

> 状态: pending | 版本: v1.0 | 关联: M2.3-OPERATION-LEVEL-ROLLOUT-PLAN
> 基础: `.omo/standards/operation-levels.md` (v1.0)
> 范围: 所有 MCP/tool 到 L0-L3 的分层分类，不包含代码实现

---

## 1. MCP/Tool Inventory

### 1.1 KOS MCP

| Tool | Current Level | Target Level | Deny Path | Notes |
|------|:------------:|:------------:|:---------:|-------|
| search_knowledge | — | L0 | none | read-only |
| get_knowledge | — | L0 | none | read-only |
| get_system_status | — | L0 | none | read-only |
| get_entity | — | L0 | none | read-only |
| get_relation | — | L0 | none | read-only |
| cross_domain_sync (incremental) | — | L1 | audit | known safe write |
| add_tag | — | L1 | audit | known safe write |
| remove_tag | — | L1 | audit | known safe write |
| log_ingest | — | L1 | audit | known safe write |
| run_indexer (full) | L2 | L2 | _confirmed:false | align to existing server.py:398 |
| run_indexer (incremental) | L1 | L1 | audit | align to existing server.py:463 |
| ontology_rebuild | — | L2 | _confirmed:false | align to existing server.py:486 |
| delete_knowledge | — | L2 | _confirmed:false | |
| db_vacuum | — | L3 | _confirmed:false + 24h | |
| db_drop | — | L3 | _confirmed:false + 24h | |

### 1.2 Agora Registry

| Tool | Current Level | Target Level | Deny Path | Notes |
|------|:------------:|:------------:|:---------:|-------|
| list_services | — | L0 | none | |
| check_health | — | L0 | none | |
| resolve_uri | — | L0 | none | |
| register_service | — | L1 | audit | auto-discovery |
| update_service_config | — | L2 | _confirmed:false | |
| unregister_service | — | L2 | _confirmed:false | |
| registry_db_reset | — | L3 | _confirmed:false + 24h | |

### 1.3 Eidos MCP

| Tool | Current Level | Target Level | Deny Path | Notes |
|------|:------------:|:------------:|:---------:|-------|
| validate | — | L0 | none | |
| list_schemas | — | L0 | none | |
| register_schema | — | L2 | _confirmed:false | |
| unregister_schema | — | L2 | _confirmed:false | |

### 1.4 gbrain MCP

| Tool | Current Level | Target Level | Deny Path | Notes |
|------|:------------:|:------------:|:---------:|-------|
| get_page | — | L0 | none | |
| list_pages | — | L0 | none | |
| search | — | L0 | none | |
| put_page | — | L1 | audit | |
| add_tag | — | L1 | audit | |
| remove_tag | — | L1 | audit | |
| delete_page | — | L2 | _confirmed:false | |
| softDeletePage | — | L2 | _confirmed:false | |
| purgeDeletedPages | — | L2 | _confirmed:false | |
| executeRaw(DELETE/DROP) | — | L3 | _confirmed:false + 24h | |

### 1.5 agentmesh Tools

| Tool | Current Level | Target Level | Deny Path | Notes |
|------|:------------:|:------------:|:---------:|-------|
| list_tools | — | L0 | none | |
| get_tool | — | L0 | none | |
| list_agents | — | L0 | none | |
| run_agent | — | L1 | audit | |
| register_tool | — | L2 | _confirmed:false | |
| unregister_tool | — | L2 | _confirmed:false | |
| stop_agent | — | L2 | _confirmed:false | |

### 1.6 SharedBrain MCP

| Tool | Current Level | Target Level | Deny Path | Notes |
|------|:------------:|:------------:|:---------:|-------|
| bos_health | — | L0 | none | |
| bos_status | — | L0 | none | |
| bos_task_submit | — | L1 | audit | |
| bos_task_list | — | L0 | none | |
| bos_organ_status | — | L0 | none | |
| bos_organ_delegate | — | L2 | _confirmed:false | |
| bos_organ_reset | — | L3 | _confirmed:false + 24h | |

---

## 2. Classification Rules

### 2.1 L0 — Read-Only (搜索/查询/列表/状态)

- Must NOT modify any persistent state
- Must NOT trigger side effects (logging is acceptable)
- Examples: search, get, list, status, health, validate

### 2.2 L1 — Low-Risk Write (增添/标记/缓存/增量)

- Known-safe mutations with clear undo path
- Must log to audit trail
- Examples: add_tag, log_ingest, incremental_sync, auto-register

### 2.3 L2 — High-Risk Write (删除/重建/批量修改)

- May affect data integrity or availability
- **Must require human confirmation** (`_confirmed: true`)
- Default: deny with `PermissionError`
- Examples: delete, full_reindex, schema_modify, batch_operation

### 2.4 L3 — Destructive (清空/重置/不可逆)

- Irreversible operations
- **Must require human confirmation** AND **24h cool-down**
- Default: deny with `PermissionError`
- Examples: db_drop, factory_reset, purge_all

---

## 3. Deny Path Standard

Per `operation-levels.md` §3:

```
L2 deny pattern:
  confirmed = args.pop("_confirmed", false)
  if not confirmed:
    raise PermissionError("L2 operation '{tool}' requires _confirmed=true")

L3 deny pattern:
  confirmed = args.pop("_confirmed", false)
  cooldown = args.pop("_cool_down_hours", 0)
  if not confirmed or cooldown < 24:
    raise PermissionError("L3 operation requires _confirmed=true AND cooldown>=24h")
```

### Aligned with KOS MCP Existing Annotations

KOS MCP `server.py` already implements `operation_level` annotations at:
- Line 398: `run_indexer(full)` → L2
- Line 463: `run_indexer(incremental)` → L1
- Line 486: `ontology_rebuild` → L2

This rollout plan aligns with and extends these existing annotations.

---

## 4. Human Approval Standard

### 4.1 When Approval is Required

| Level | Approval | Method | Audit |
|:----:|----------|--------|:----:|
| L0 | never | — | optional |
| L1 | never (audit only) | log | required |
| L2 | required | `_confirmed: true` | required |
| L3 | required + 24h cool-down | `_confirmed: true` + `_cool_down_hours >= 24` | required |

### 4.2 Approval Request Format

```json
{
  "tool": "run_indexer",
  "level": 2,
  "_confirmed": false,
  "args": {"zone": "sharedbrain"},
  "evidence": {
    "drift_detected": "total=-15%, zone=sharedbrain",
    "known_doc_retrieval": "10/10"
  },
  "requested_by": "kos-drift-monitor",
  "requested_at": "2026-05-30T10:00:00Z"
}
```

---

## 5. First-Wave Minimum Viable Candidates

### Selection Criteria
- Cover each level (L0/L1/L2/L3) with at least 1 tool
- Align with existing KOS MCP annotations (server.py:398, 463, 486)
- Do NOT touch sensitive capabilities (Apple/WeChat/Family OS/SMB/Media)

### Candidate Set

| # | Tool | Level | Rationale |
|:-:|------|:----:|-----------|
| 1 | `kos search_knowledge` | L0 | already read-only, lowest risk |
| 2 | `kos run_indexer(incremental)` | L1 | already annotated as L1 in server.py:463 |
| 3 | `kos run_indexer(full)` | L2 | already annotated as L2 in server.py:398, deny path exists |
| 4 | `gbrain delete_page` | L2 | clear L2 pattern, deny path straightforward |
| 5 | `kos db_vacuum` | L3 | destructive + reversible enough for first L3 test |

### Why These 5

1. **L0 validation**: confirm read-only works without any deny path
2. **L1 validation**: confirm audit logging works for known-safe writes
3. **L2 with existing deny path**: confirm KOS MCP already-implemented pattern works
4. **L2 new deny path**: confirm deny path can be extended to a new tool
5. **L3 cooldown**: confirm 24h cool-down mechanism works end-to-end

---

## 6. Rollout Sequence

```
Wave 1 (immediate):    Tool inventory + classification table    ← this document
Wave 2 (M2.3 exec):    Deny path implementation for 5 candidates
Wave 3 (M2.4):         Remaining MCP tools classification
Wave 4 (M2.5):         All denly paths implemented → full rollout complete
```

---

## 7. Sensitive Capabilities Blocked

Canonical policy phrase: **sensitive capabilities remain blocked**.

These capabilities must maintain L2/L3 deny paths at minimum:

- Apple ecosystem connectors (Calendar, Reminders, Notes)
- WeChat message/file access
- Family OS scheduler (member profiles, health records)
- SMB/NAS file operations
- Media indexing (photos, videos)
- High-autonomy triggers (>50% autonomous operations)

**Rule**: Any new tool that touches one of these domains must be classified at L2 or L3 by default. Reclassification to L0/L1 requires human approval.

---

> **Evidence required**: MCP tool inventory table ✓ | Classification table ✓ | Deny path standard ✓ | Human approval standard ✓ | First-wave candidates ✓ | Sensitive capabilities blocked ✓
