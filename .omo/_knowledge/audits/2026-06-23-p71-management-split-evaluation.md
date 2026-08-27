---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P71 评估报告: management/ 142 拆 3 类 (大重构前评估)

**日期**：2026-06-23
**评估目标**：在 P53 候选中标记为"大重构, 需深度访谈", P71 先做评估不实际拆分

## 1. 现状摸底

```
total_files: 144 (含 README/INDEX)
status: archived: 142 (99%)
status: active: 1
status: experimental: 0
```

## 2. 4 维度评估

| 维度 | 评分 | 原因 |
|------|-----:|------|
| **价值 (Value)** | 4/10 | 142 个 archived 历史快照, 当前无活跃引用, 价值低 |
| **工作量 (Effort)** | 8/10 | 拆分类目需重新组织 frontmatter + INDEX 更新, 至少 5 个文件改动 |
| **风险 (Risk)** | 7/10 | 改 frontmatter 影响 .omo lint doc-lifecycle (P45), 需 lint 跳过 archived |
| **可达性 (Reachability)** | 5/10 | 142 文件多, 需深度访谈确认分类标准 |

**总分**: 24/40 = 60% (中等)

## 3. 拆分计划草案 (P71 评估, 待 P73+ 实施)

**目标**: 把 management/ 拆为 3 类, 沿 P45 frontmatter 4 字段契约

### 3.1 拆分类目

| 类目 | 当前数量 | 拆分标准 | 目标路径 |
|------|---------:|----------|----------|
| `workflows/` | ~50 | 含 "workflow" / "process" 流程指南 | `.omo/_knowledge/management/workflows/` |
| `playbooks/` | ~50 | 含 "playbook" / "runbook" / "how-to" 操作手册 | `.omo/_knowledge/management/playbooks/` |
| `guides/` | ~42 | 含 "guide" / "intro" / "explainer" 概念解释 | `.omo/_knowledge/management/guides/` |

### 3.2 实施步骤 (估计 5-8 commits)

1. **P73**: 评估 142 文件 frontmatter, 分类映射
2. **P74**: 在每个文件加 `category: workflows/playbooks/guides` 字段
3. **P75**: 物理迁移 (用 P53 双指针模式: 原位 deprecated + 新位 active)
4. **P76**: 更新 INDEX.md + 验证 lint 不报错
5. **P77**: 删除原 management/ 目录 (双指针已生效)

### 3.3 风险缓解

- **风险 1**: lint doc-lifecycle 把新 frontmatter 误报 → 提前在 omo_lint 加 `category` 白名单
- **风险 2**: 引用断裂 (其它文件 link 到 management/*.md) → 全局搜索替换 + 保留 deprecated 指针
- **风险 3**: pre-commit 钩子过严 → 已验证 ruff 通过, 主要是 mof-schema-validate

### 3.4 价值评估

**短期** (P73-P77): 治理成熟度 +1 (类目清晰), 检索效率 +30%
**长期**: 文档维护成本降低, 但 archived 文档价值持续衰减
**风险**: 142 文件迁移是单向操作, 出错恢复成本高

## 4. 推荐

**P72+ 暂不实施, 优先做**:
- **P72 #1**: governance-agent 7 步 (加 dim-weight 评估)
- **P72 #2**: alert-history 加 sup_state 维度 (从 P71 by_cross_level 扩展)
- **P72 #3**: dim-weight 调优 (基于历史相关性的更稳健算法)

**P75+ 实施拆分**, 但需先:
- 评估 1-2 个具体文件确认分类标准
- 与人类用户访谈确认使用习惯

## 5. 元数据

- 评估人: governance-team
- 评估方法: 4 维度 (Value/Effort/Risk/Reachability)
- 评估时间: 2026-06-23
- 关联 ADR: ADR-0053 (doc-lifecycle), ADR-0054 (P60 治理方法论)
