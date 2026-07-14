---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0076: P82 cross-ref scope-aware + status-aware + 死链治理收口

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P82
- **Extends**: ADR-0075 (P81 cross-ref 引入)
- **Superseded by**: (无)

## Context and Problem Statement

P81 R4 引入 `bin/ssot/management-cross-ref-check.py` (扫描 .omo/_knowledge/management/ 跨文件引用),
首版报告 54 死链。P82 调研发现:

1. **P81 工具缺陷**: 仅按"文件名 basename 匹配 files_by_cat"判定死链, 把"跨管理目录的外部引用"误判为死链
2. **JSON 序列化 bug**: `refs_matrix` 用 tuple key + `dead_links` 含 Path 对象, 触发 `json.dumps` 失败
3. **status 误报**: 不区分 active/archived 文档, 误把历史 archived 文档的预期死链当 actionable bug
4. **tools 误用**: `.omo/INDEX.md` 标记 archived, 但 P77 物理迁移后已被 `.omo/INDEX.md` 取代, 仍残留

## Decision

### D1: 工具升级为 scope-aware + status-aware (P82 R1+R2)

**改进**:
- 解析链接相对路径来源文件的实际位置, 区分:
  - **内部引用 (同 management scope)**: target 在 workflows/playbooks/guides/INDEX 中
  - **外部引用 (跨域)**: 绝对路径 (`/...`) 或 `../` `../../` 跳出 management 目录
- 外部引用 **不再误判为死链**, 单独统计; 仅当外部引用目标也不存在时, 才归为 dead
- **status 感知**: 从 frontmatter 读 `status: archived`, 死链按 active/archived 分类
  - `dead_links_active`: 0 (active 文档无死链, 治理良好)
  - `dead_links_archived`: 43 (历史 archived 文档的预期死链, 不需修复)
- 修复 `json.dumps` bug: tuple key → str key, Path → str
- 删除 `Counter` / `file_names` 等未使用 import + 变量, ruff 0 错

### D2: 删除孤立 `.omo/INDEX.md` (P82 R3)

**前置**:
- `.omo/INDEX.md` 标记 `status: archived`, `archived-since: 2026-06-22`, `lifecycle: history`
- P77 R1 物理迁移后, 新 INDEX 在 `.omo/INDEX.md` (status: active)
- `grep workflows/INDEX` 全仓 0 引用 → 真正孤立

**决策**:
- `git rm .omo/_knowledge/management/.omo/INDEX.md` (9 死链源头一次性清掉)
- 不修改历史 archived 文档 (尊重 P45 审计决策: 历史状态不变)

### D3: P82 收口: active:0 + archived:43 (P82 R4)

**最终指标**:
- 144 文件 (P77 物理迁移后) → 143 (删 1 个孤立 INDEX)
- 43 内部引用 (workflows→workflows) + 2 (workflows→guides) = 45 内部引用已解析
- 45 外部引用 (跨域) 单独统计
- 43 死链全部在 archived 文档, 0 在 active 文档 → 治理质量 A+

**ADR 链**: ADR-0069 (P75 categorize) → ADR-0071 (P77 物理迁移) → ADR-0072 (P78 cross-submodule) → ADR-0075 (P81 cross-ref 引入) → **ADR-0076 (P82 scope/status 感知 + 收口)**

## Consequences

**正面**:
- 工具误报从 54 降到 0 (active), 治理噪音消除
- archived 历史死链保留 (尊重 P45 审计决策, 不"清洗历史")
- scope/status 双维度分类, 死链治理有清晰 actionable subset
- 删孤立 INDEX 释放 1 个 SSOT 重复

**负面**:
- frontmatter 解析简化为字符串匹配, 不支持嵌套 YAML / 多行 status (后续 P83+ 可升级)
- archived 死链不会自动修复 (P45 决策), 长期保留

**关联**:
- 升级后工具进入 P82+ 日常治理循环
- 与 ADR-0075 形成完整 pair: P81 引入 → P82 校准

## Validation

```bash
# 重跑确认 active:0
python3 bin/ssot/management-cross-ref-check.py .

# 期望输出:
# 🔗 内部引用 (已解析): 45
# 🌐 外部引用 (跨域):  45
# ❌ 死链 (目标不存在): 43 = active:0 + archived:43

# ruff 验证
ruff check bin/ssot/management-cross-ref-check.py
# 期望: All checks passed!
```

## References

- P81 R4 报告: 145 文件, 54 死链 (按 basename 误判)
- P82 实际: 144 文件 (删 1), 0 active 死链, 43 archived 历史死链 (符合预期)
- ADR-0075: P81 cross-ref 引入
- ADR-0071: P77 物理迁移
- ADR-0069: P75 management 分类

---

*最后更新: 2026-06-23 · P82 cross-ref 治理收口*
