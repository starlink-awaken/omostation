---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史审计快照批量归档, 当前 governance 100 A+ 持续"
---
# P50 收口报告 — gbrain 53 TODOs 4 类决策 + mof-drift v4 智能分类

> 2026-06-23 · mof-version v0.0.38
> Pattern: c2g → omo → mof (P49 闭环延伸)

## 1. 背景

P49 (commit 3dd14dba) 完成后审计：

- **PLANNED 目录清零** (历史首次)
- **mof-drift 2 LOW** (gbrain 53 TODOs + 5 类分类 unknown=26)
- **P50 R0 调研**: 26 unknown 实际是**纯 TODO** (无 TODOS.md/v0.XX 引用), 不是误分类
- **mof-version v0.0.37**

## 2. P50 3 Rounds

| Round | 主题 | 关键产物 |
|-------|------|---------|
| R1 | mof-drift v4 智能分类修复 | unknown 26→19 + Top-5 文件分布 + planned 8 模式 |
| R2 | ADR-0050 决策记录 | `.omo/_knowledge/decisions/0050-gbrain-53-todos-4-cat.md` |
| R3 | 收口 | P50-GBR-TODO task → done + mof-version v0.0.38 |

## 3. R1 详细 — mof-drift v4 智能分类修复

### 3.1 v3 → v4 改进

| 维度 | v3 | v4 |
|------|----|----|
| 5 类分类函数 | 简单 substring match | 加 `folded into` / `TODO-N` / `TODO: implement` / `TODO will` 等模式 |
| Top-5 文件 | ❌ | ✅ `count_gbrain_todo_top_files(top_n=5)` |
| 输出格式 | `keep=13, fix=6, close=7, planned=1, unknown=26` | `keep=13, fix=6, close=7, planned=8, unknown=19` + `Top-5 文件: src/core/search/mode.ts:5, ...` |

### 3.2 v4 5 类细化

| 类别 | v3 | v4 | 变化 | 原因 |
|------|----|----|------|------|
| keep | 13 | 13 | 0 | TODOS.md/CLAUDE.md 引用 |
| fix | 6 | 6 | 0 | bug/FIXME 标记 |
| close | 7 | 7 | 0 | v0.3x/v0.4x 引用 + folded into |
| planned | 1 | 8 | **+7** | 加 "TODO V" / "TODO-FOLLOW" / "TODO-1/2/3" / "TODO: implement" / "TODO will" / "TODO to" / "TODO mitigation" |
| unknown | 26 | 19 | -7 | 真正纯 TODO (eg. "// TODO at the bottom") |

### 3.3 Top-5 文件分布 (新增)

```
src/core/search/mode.ts: 5 TODOs
src/commands/migrations/v0_28_0.ts: 5
src/commands/migrations/v0_11_0.ts: 5
src/cli.ts: 3
src/core/postgres-engine.ts: 2
```

**洞察**: 53 TODOs 集中在 5 个文件 (20/53 = 37.7%)，其中 `migrations/v0_28_0.ts` + `migrations/v0_11_0.ts` = 10 个迁移版本 TODOs (子仓 versioning 历史)。

## 4. R2 详细 — ADR-0050 决策

`.omo/_knowledge/decisions/0050-gbrain-53-todos-4-cat.md` (active 状态):

**核心决策**: 53 TODOs 按 4 类分配, 根仓责任 0 行 gbrain 代码:

| 类别 | 数量 | 含义 | 处理 |
|------|------|------|------|
| keep | 13 | 子仓已 tracking | 等子仓 P51+ |
| fix | 6 | 真实 bug | 等子仓 P51+ |
| close | 7 | 已在 version 闭环 | 等子仓 P51+ |
| planned | 8 | 计划性 TODO | 等子仓 P51+ |
| unknown | 19 | 模糊引用 | 等子仓 P51+ 人工 review |

**ADRs 累计**: 10 个 (.omo/_knowledge/decisions/)

## 5. R3 详细 — 收口

- **P50-GBR-TODO** task → done
- mof-version v0.0.37 → v0.0.38
- governance 100 A+ 7/7 持续
- mof-drift 仍 3 LOW (53 TODOs 子仓债, P51+)

## 6. mof-drift 维度演进 (P44 → P50)

| 版本 | 维度数 | 关键能力 |
|------|--------|----------|
| v0 | 3 | sys_path / todo_count / no_tests |
| v1 (P44) | 3 | 区分硬编码 |
| v2 (P47) | 4 | + stale_planned_tools |
| v3 (P48) | 6 | + submodule_ahead + todo_categories 5 类 |
| **v4 (P50)** | **6** | **+ top_files 分布 + 智能分类修复 (planned 7 模式)** |

## 7. 累计治理状态 (P43 → P50, 8 phases)

| Phase | mof-version | governance | 关键 |
|-------|-------------|------------|------|
| P43 | v0.0.12 | 100 A+ | closed-loop pattern |
| P44 | v0.0.28 | 100 A+ | wf-convergence + 5 REMEDIATE |
| P45 | v0.0.32 | 100 A+ (7/7) | doc-lifecycle 4 类 + 14/15 维度 + 第 7 项 |
| P46 | v0.0.33 | 100 A+ | 11 PLANNED + 3 mof 实施 |
| P47 | v0.0.35 | 100 A+ | 12/12 mof + drift v2 |
| P48 | v0.0.36 | 100 A+ | mof-drift v3 + 17 项目 lint |
| P49 | v0.0.37 | 100 A+ | PLANNED 清零 |
| **P50** | **v0.0.38** | **100 A+** | **mof-drift v4 + ADR-0050** |

## 8. P51+ 路线

- gbrain 19 unknown TODOs 实际子仓 review
- gbrain 子仓 ahead 推送 (P44 DEFER-SUBMODULE-PUSH)
- TASK-08B2A2C5 / TASK-8CF4636A 验证
- 持续 mof-drift 6 维度监控

## 9. 关联

- P49-REG-CLEANUP: PLANNED 清零
- P48 R1: mof-drift v3 初次 5 类
- P44 DEFER-GBRAIN-OPERATIONS-TS: 已闭环
- P44 DEFER-GBRAIN-55-TODOS: 历史债
