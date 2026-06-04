# L0-L3 Operation Levels — Phase 2 Safe Mesh

> 状态: active | 版本: v1.0 | 关联: M2.2-OPERATION-LEVELS
> 适用范围: 所有 MCP tool、Agent action、CLI 命令

---

## 1. 级别定义

| 级别 | 名称 | 含义 | 示例 | 审批要求 |
|------|------|------|------|----------|
| **L0** | Read-Only | 纯读操作，无副作用 | 搜索、查询、列出、健康检查 | 无 |
| **L1** | Low-Risk Write | 低风险写，已确认安全 | 添加 tag、记录日志、更新缓存 | 审计记录即可 |
| **L2** | High-Risk Write | 高风险写，可能影响数据完整性 | 索引重建、批量删除、Schema 修改 | **必须人工确认** |
| **L3** | Destructive | 破坏性操作，不可逆 | 删除数据库、清空索引、回滚版本 | **人工确认 + 24h 冷静期** |

## 2. 操作分类矩阵

每个操作必须标记其 operation_level。以下为默认分类：

```
Pages CRUD (gbrain/SharedBrain):
  get_page, list_pages, search                      → L0
  put_page, add_tag, remove_tag, log_ingest          → L1
  delete_page, softDeletePage, purgeDeletedPages     → L2
  executeRaw(DELETE/DROP/TRUNCATE)                   → L3

KOS Index:
  search_knowledge, get_knowledge, get_system_status → L0
  cross_domain_sync (incremental)                    → L1
  run_indexer (full), ontology_rebuild               → L2
  kos db vacuum, kos db drop                         → L3

Agora Registry:
  list_services, check_health                        → L0
  register_service (auto-discovery)                  → L1
  unregister_service, update_service_config          → L2
  registry db reset                                  → L3

Config:
  get_config, list_config_keys                       → L0
  set_config (existing key)                          → L1
  set_config (new key), unset_config                 → L2
  config factory reset                                → L3
```

## 3. 拒绝路径（Deny Path）

L2 操作未确认时必须被拒绝。拒绝路径：

```python
# MCP tool middleware pattern
def _check_operation_level(level: int, tool_name: str, args: dict) -> None:
    if level >= 2:
        confirmed = args.pop("_confirmed", False)
        if not confirmed:
            raise PermissionError(
                f"L{level} operation '{tool_name}' requires explicit confirmation. "
                f"Re-run with `_confirmed: true` after review."
            )
    if level >= 3:
        confirmed = args.pop("_confirmed", False)
        cooldown = args.pop("_cool_down_hours", 0)
        if not confirmed or cooldown < 24:
            raise PermissionError(
                f"L3 operation '{tool_name}' requires explicit confirmation "
                f"AND 24h cool-down. Set `_cool_down_hours: 24`."
            )
```

## 4. 审计日志

每次 access/deny 必须记录：

```yaml
# Audit log entry schema
operation_level: L0|L1|L2|L3
tool: tool_name
action: allow|deny
actor: agent_id|human
target: resource_path
reason: "explicit confirmation missing" | "cool-down not satisfied" | "auto-approved"
timestamp: ISO-8601
```

审计日志存储位置：`~/.omostation/audit/operations.log`

## 5. 测试场景

| 场景 | 输入 | 预期输出 | 验证 |
|------|------|----------|------|
| L0 正常执行 | `get_page("hello")` | 返回 page | ✅ |
| L1 自动通过 | `add_tag("hello", "test")` | 成功，有审计 | ✅ |
| L2 无确认被拒 | `delete_page("hello")` | **拒绝**: PermissionError | ✅ 必须验证 |
| L2 有确认通过 | `delete_page("hello", {_confirmed: true})` | 成功，有审计 | ✅ |
| L3 无冷静期被拒 | `executeRaw("DROP TABLE pages", {_confirmed: true})` | **拒绝**: 需 24h | ✅ 必须验证 |
| L3 冷静期通过 | `executeRaw("DROP TABLE pages", {_confirmed: true, _cool_down_hours: 24})` | 成功，有审计 | ✅ |

## 6. 集成方案

Phase 2 不要求所有 MCP server 立即实现 operation level middleware，但要求：

1. **定义已完成**（本文件）✅
2. **Agora 注册表**支持为每个已注册 tool 标注 operation_level
3. **agentmesh Gateway** 支持在 dispatch 时检查 operation_level
4. **审计日志 schema** 已定义并写入 ops/hermes

当前阶段优先级：完成定义和 Agora 注册表集成。

---

## 7. Rollout inventory baseline

本节吸收原 `operation-level-rollout-plan.md` 的最小 rollout 约束。

### 7.1 First-wave candidate set

| Tool / Action | Target Level | Deny Path |
|---------------|--------------|-----------|
| `kos search_knowledge` | L0 | none |
| `kos run_indexer(incremental)` | L1 | audit |
| `kos run_indexer(full)` | L2 | `_confirmed: true` |
| `gbrain delete_page` | L2 | `_confirmed: true` |
| `kos db_vacuum` | L3 | `_confirmed: true` + `24h` |

### 7.2 Rollout sequence

1. 建 inventory / classification table
2. 为 first-wave tools 落 deny path / audit path
3. 扩展到更多 MCP/tool surface
4. 最后才允许默认放大到全量 rollout

### 7.3 Sensitive capability rule

以下能力在独立 gate 前保持 blocked：

- Apple / WeChat / Family OS
- 高自主自愈
- 未完成审批链的 destructive admin action

### 7.4 Phase 8 blocked-surface ratification criteria

Phase 8 结束时，这些 blocked surface 的扩张必须同时满足：

1. 已有 repo 内 governance posture 被明确记录并可引用
2. cross-repo AGENTS / governance sync 已完成独立 planning gate
3. 对应 surface 的 approval / audit / rollback 路径都被写成显式证据，而不是口头约定

在以上条件完成前，Apple / WeChat / Family OS 继续保持 blocked，不得因为 Phase 8 control plane 落地而自动解锁。
