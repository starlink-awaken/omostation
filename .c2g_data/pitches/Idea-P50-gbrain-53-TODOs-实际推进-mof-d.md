# P50 gbrain 53 TODOs 实际推进 + mof-drift v4 智能分类修复 + 子仓 ahead 推送

> **Upstream**: P49-REG-CLEANUP (mof-version v0.0.37) / OMO 100 A+ 持续
> **Appetite:** 1.5 day
> **Vector:** V2 (c2g brainstorm 转化)
> **Type:** Feature + 治理收敛

## 背景与上下文

P49 (commit 3dd14dba) 完成后审计：

- **PLANNED 目录清零** (历史首次)
- **mof-drift 2 LOW**:
  - gbrain 53 TODOs found in gbrain
  - gbrain TODOs: keep=13, fix=6, close=7, planned=1, unknown=26
- **关键发现 (P50 R0)**: 26 unknown TODOs 实际**全部隐含 TODOS.md / CLAUDE.md / V0.XX 引用** — P48 R1 分类函数过严
- **gbrain 0 ahead** (子仓已 fetch 同步)
- **mof-version v0.0.37**

## 目标

### P50 R1 (今天, 0.5h) — 立项 + mof-drift v4 智能分类修复
- **G1**: c2g bet → omo broker → P50-GBR-TODO PLANNED task
- **G2**: mof-drift v4: 修 todo_categories 分类 (unknown 26 → 实际 0, 全归 keep/fix/close/planned)
- **G3**: 新增"按文件 Top-N"维度 (53 TODOs 分布报告)

### P50 R2 (今天, 0.5h) — gbrain 53 TODOs 推进
- **G4**: 创建根仓治理 track: `.omo/_knowledge/decisions/2026-06-23-p50-gbrain-todo-classification.md`
- **G5**: 4 类决策 (按实际状态):
  - keep=13 → 标 `status: tracked` (引用子仓 tracking, 不动)
  - fix=6 → 标 `status: bug-pending` (等子仓 P51+)
  - close=7 → 标 `status: versioned` (引用 v0.3x/v0.4x, 等子仓)
  - planned=1 → 标 `status: planned` (TODO vX.X)
  - unknown=26 → 重新分类 (大部分引用 TODOS.md, 实际归 keep)
- **G6**: 治理推进为 P50-PLAN 跟踪 (子仓行动)

### P50 R3 (今天, 0.5h) — 收口
- **G7**: P50-GBR-TODO task → done
- **G8**: mof-version v0.0.37 → v0.0.38
- **G9**: 收口报告入 `.omo/_knowledge/audits/`
- **G10**: governance 100 A+ 持续

## 技术要求

- **零代码改动**: 不动 gbrain 子仓任何代码 (P50 仅根仓治理)
- **mof-drift v4 扩展**: 沿用 v3 模式 (排除自指, 触发条件)
- **决策记录**: 用 omo standard 模式 (`.omo/_knowledge/decisions/`)

## 验收标准

1. **G1** P50-GBR-TODO PLANNED task 创建
2. **G2** mof-drift v4 报告 unknown ≤ 5 (实际归类)
3. **G3** mof-drift 报告 Top-N TODO 分布
4. **G4-G5** 53 TODOs 4 类决策记录入 .omo/_knowledge/decisions/
5. **G7-G9** task done + mof-version v0.0.38 + 收口报告
6. **G10** governance 100 A+ 持续

## 风险

| 风险 | 缓解 |
|------|------|
| mof-drift 改 v3 → v4 误报 | 沿用 v3 模式 + 单元测试 (manually) |
| gbrain 子仓 ahead 推送 CI 悬空 | P50 不推 (P51+ 推) |
| 53 TODOs 决策误判 | 仅根仓治理 track, 不改子仓 |

## 关联

- P49-REG-CLEANUP: PLANNED 清零
- P48 R1: mof-drift v3 (5 类初次)
- P44 DEFER-GBRAIN-OPERATIONS-TS: operations.ts 拆分
- P44 DEFER-GBRAIN-55-TODOS: gbrain 55 TODOs (早期债)

## NoGos (YAGNI)

- ❌ 不推 gbrain 子仓 ahead (P51+)
- ❌ 不实施 53 TODOs (子仓工作)
- ❌ 不删任何 gbrain 代码
- ❌ 不改 mof-drift 现有 6 维度
