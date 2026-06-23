---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# KOS Index Repair Plan — M2.1

> 状态: plan (待人工审批) | 关联: M2.1-KOS-INDEX-DIAGNOSIS
> 根因: `engine.py` L1016-1027 的 absent-file cleanup 使用 `get_zone_path()` 而非实际扫描路径

---

## 1. 修复前准备（Backup/Snapshot）

| 步骤 | 操作 | 回滚条件 |
|------|------|----------|
| 1.1 | `cp ~/.kos/kos-index.sqlite ~/.kos/kos-index.sqlite.bak.$(date +%Y%m%d)` | 回滚: `cp .bak 恢复` |
| 1.2 | `kos get_system_status` → 记录当前文档数、zone 分布 | 对比 before/after |
| 1.3 | `sqlite3 ~/.kos/kos-index.sqlite "SELECT COUNT(*) FROM documents"` | 硬计数校验 |
| 1.4 | 记录 `file_fingerprints` 表 absent_since 分布 | 诊断 false-absent 范围 |

## 2. 修复步骤（Code + Reindex）

### 2.1 代码修复

修改 `src/kos/indexer/engine.py` L1016-1027：

```python
# BEFORE (buggy):
for zone_id in indexed_zones:
    zone_path = Path(get_zone_path(zone_id))
    fps = conn.execute(...)
    for fp in fps:
        if not (zone_path / fp["canonical_path"]).exists():
            conn.execute("UPDATE file_fingerprints SET absent_since=?", ...)

# AFTER (fixed):
for zone_id in indexed_zones:
    zone_config = zc.get(zone_id, {})
    scan_roots = _get_scan_roots(zone_id, zone_config)  # includes custom path + additionalPaths
    fps = conn.execute(...)
    for fp in fps:
        exists = any((root / fp["canonical_path"]).exists() for root in scan_roots)
        if not exists:
            conn.execute("UPDATE file_fingerprints SET absent_since=?", ...)
```

同时添加 `_get_scan_roots()` 辅助函数复用 `_iter_zone_files` 的路径逻辑。

### 2.2 Dry-Run 验证

```bash
# 步骤 1: 备份
cp ~/.kos/kos-index.sqlite{,.bak}

# 步骤 2: 应用代码修复

# 步骤 3: Dry-run — 只标记不改
kos index --incremental --dry-run
# 预期: 不会新增 false-absent 标记

# 步骤 4: 全量重建（恢复丢失文档）
kos index  # 全量重建
# 预期: 文档数恢复到接近原始值

# 步骤 5: 验证
kos get_system_status
sqlite3 ~/.kos/kos-index.sqlite "SELECT COUNT(*) FROM documents"
```

### 2.3 Write-Pause 条件

以下情况 **暂停写入，不执行修复**：
- `kos get_system_status` 返回 ERROR 或 DB 损坏
- 备份文件校验失败（`sha256sum` 不匹配）
- 当前文档数 < 100（表明比预期退化更严重，需人工介入）

## 3. 10 Known Documents Verification List

修复后必须验证以下 10 个已知文档可检索：

```
# 执行 kos search <query> 验证每个返回结果
1. "Phase 1 复盘报告"          → 应返回 phase1-retrospective.md
2. "MCP 标准化规范"             → 应返回 MCP_STANDARDS.md
3. "SharedBrain B-OS"           → 应返回 SharedBrain 相关文档
4. "Agora MCP Server"           → 应返回 agora server/mcp.py
5. "KOS 索引引擎"               → 应返回 kos indexer/engine.py
6. "Eidos format_version"       → 应返回 eidos mcp_server.py
7. "LAYER-INDEX"               → 应返回 LAYER-INDEX.md
8. "memU Engine"               → 应返回 memu-engine.ts
9. "LiteLLM Adapter"           → 应返回 litellm.ts
10. "sharedbrain-bridge"       → 应返回 bridge 包文档
```

验证命令模板：
```bash
for q in "Phase 1 复盘" "MCP 标准化" "SharedBrain" "Agora MCP" "KOS 索引" "Eidos" "LAYER" "memU" "LiteLLM" "bridge"; do
  result=$(kos search "$q" --limit 1 --json 2>/dev/null)
  count=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('results',[])))" 2>/dev/null || echo 0)
  echo "[$count] $q"
done
```

验收标准：10/10 返回 >0 结果。

## 4. Risk Assessment

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 修复后仍无法找回文档 | 低 | 高 | 备份可回滚，手工恢复 |
| 代码修复引入新 bug | 中 | 中 | Dry-run 先行，CI 测试 |
| 全量重建耗时过长 | 中 | 低 | 可在后台运行 |
| 索引期间性能下降 | 低 | 中 | 非工作时间执行 |

## 5. Approval Gate

**人工审批条件**：
- [ ] 备份文件存在并可恢复校验
- [ ] Dry-run 通过（无异常 false-absent）
- [ ] 10 known docs 当前不可检索的比例已记录
- [ ] 修复窗口已安排（建议非工作时间）

**审批人**: human + verifier
**预计执行时间**: 30-60 分钟
**回滚命令**: `cp ~/.kos/kos-index.sqlite.bak ~/.kos/kos-index.sqlite`
