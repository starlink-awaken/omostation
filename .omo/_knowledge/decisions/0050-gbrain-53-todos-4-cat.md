---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0050: gbrain 53 TODOs 4 类决策 (P50 R2)

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P50
- **Supersedes**: P44 DEFER-GBRAIN-55-TODOS (历史债 55→53)
- **Superseded by**: (无)

## Context and Problem Statement

P44 R0 DEBT-GBRAIN-OPERATIONS-TS 已完成（operations.ts 3841 行拆分）。但 P48 R1 审计发现 gbrain 仍有 **53 个 TODO 散落**在 7+ 个核心文件，**根仓无法识别分类**——既影响 mof-drift 报告，又无法做精准推进。

P50 R0 调研:
- 53 TODOs 实际是子仓内的功能性注释，**不是子仓代码债**
- mof-drift v3 智能分类已能 keep=13 / fix=6 / close=7 / planned=8 / unknown=19 (P50 v4)
- Top-5 文件分布: `src/core/search/mode.ts:5`, `src/commands/migrations/v0_28_0.ts:5`, `src/commands/migrations/v0_11_0.ts:5`, `src/cli.ts:3`, `src/core/postgres-engine.ts:2`

## Decision

**P50 决策: 53 TODOs 按 4 类分配 (沿用 P48 mof-drift 分类)**:

| 类别 | 数量 | 含义 | 处理 |
|------|------|------|------|
| **keep** (13) | 引用子仓 `TODOS.md` / `CLAUDE.md` | 子仓已 tracking, 不动 | 等子仓 P51+ |
| **fix** (6) | 含 `bug` / `FIXME` | 真实 bug 待修 | 等子仓 P51+ |
| **close** (7) | 引用 `v0.3x` / `v0.4x` 或 `FOLDED INTO` | 已在子仓某个 version 闭环 | 等子仓 P51+ |
| **planned** (8) | 引用 `TODO vX.X` / `TODO-N` / `TODO: implement` | 计划性 TODO | 等子仓 P51+ |
| **unknown** (19) | 模糊引用 (eg. `// TODO at the bottom`) | 需子仓人工 review | 等子仓 P51+ |

**P50 根仓责任**:
- ✅ mof-drift v4 智能分类 (unknown 26→19, 实际更精准)
- ✅ Top-5 文件分布报告
- ✅ 本 ADR 决策记录
- ❌ **不实施**任何 gbrain TODO (子仓工作)
- ❌ **不推**子仓 ahead commits (P51+)

## Consequences

**正面**:
- mof-drift 报告从"53 TODOs"模糊描述变成"13+6+7+8+19 + Top-5 文件"细粒度
- 任何根仓 agent 启动时看本 ADR + mof-drift 一眼就知 53 TODOs 实际状态
- 子仓推 ahead 时 5 类分布不变 (只是数字更新)

**中性**:
- mof-drift v4 智能分类 vs v3 简单分类: 5 类数字微调, 但更精确
- P50 实施 0 行 gbrain 代码 (避免越权)

**负面**:
- 19 unknown 仍需子仓人工 review (P51+ 工作)
- mof-drift 维护成本增加 (v4 分类函数更复杂)

## Implementation

P50 已落地:
- `bin/mof-drift` v4: 智能分类 (P50 v4: 加 strip 标点, planned 5 模式, fixed folded into, TODO-N)
- `.omo/_knowledge/decisions/0050-gbrain-53-todos-4-cat.md`: 本 ADR
- 收口报告: `.omo/_knowledge/audits/2026-06-23-p50-gbrain-todo-closeout.md`
- mof-version v0.0.37 → v0.0.38
- governance 100 A+ 持续

## Alternatives Considered

1. **删 53 TODOs** — 不可行 (子仓代码, 根仓无权限)
2. **改 mof-drift 把 53 标 0** — 不可行 (欺骗性, 治理失真)
3. **推子仓 ahead (P50 推)** — 不可行 (P43 submodule_state_decoupling 教训: 主仓不批量 bump)

## References

- P48 R1: mof-drift v3 (5 类初次)
- P50 R1: mof-drift v4 (智能分类修复)
- P44 DEFER-GBRAIN-OPERATIONS-TS: operations.ts 拆分 (历史债)
- P44 DEFER-GBRAIN-55-TODOS: gbrain 55 TODOs (历史债)
- P50 c2g brainstorm: `.c2g_data/pitches/Idea-P50-gbrain-53-TODOs-实际推进-mof-d.md`
