# P48 gbrain 53 TODOs 推进 + 全面验证全模块架构收敛

> **Upstream**: P47 R3 (mof-drift 7→1) / OMO 100 A+ 持续
> **Appetite:** 1 day
> **Vector:** V2 (c2g brainstorm 转化)
> **Type:** Feature + 收敛

## 背景与上下文

P47 (commit ef6425b5 + 2118c6c9) 完成后审计：

- **mof-drift 7 → 1** (P47 R3 加 stale_planned_tools 维度)
- **剩余 1 LOW**: gbrain 53 TODOs found in gbrain
- **根仓** vs **子仓** 边界:
  - 根仓: mof-drift 扫 `projects/gbrain/src/`, 但 gbrain 是子仓, gitlink 在根仓
  - gbrain 子仓: 自己的 TODO 跟踪 (TODOS.md), 但根仓不可见

**关键发现**:
- `projects/gbrain/src/core/operations.ts` (23 行) **已经**拆分 (DEBT-GBRAIN-OPERATIONS-TS, 2026-06-20, 3841→多个子模块)
- 53 TODOs 分散在 7+ 个核心文件, 大多引用 `TODOS.md` (子仓 tracking)
- gbrain 15 commits ahead (P44 DEFER-SUBMODULE-PUSH)

## 目标

### P48 R1 (今天, 1h) — 立项 + 智能 drift
- **G1**: c2g bet → omo broker → P48-GBR-AHEAD PLANNED task
- **G2**: mof-drift v3 加新维度 `gbrain_ahead_commits` (扫 git submodule status ahead 数量)
- **G3**: mof-drift v3 加新维度 `gbrain_todo_categories` (按 4 类分类: keep/fix/close/supersede)

### P48 R2 (今天, 1h) — 全面验证 17 项目
- **G4**: 跑 17 项目 lint 全清单 (P44 R7 全模块 lint 87→0 之后 1 个新项目观测)
- **G5**: 跑 17 项目 test (P44 R7 之后新增)
- **G6**: 确认 governance 100 A+ 持续

### P48 R3 (今天, 0.5h) — 收口
- **G7**: P48-GBR-AHEAD task → done
- **G8**: mof-version v0.0.35 → v0.0.36
- **G9**: 收口报告入 `.omo/_knowledge/audits/`

## 技术要求

- **零路径破坏**: 不改 P45-P47 任何文件
- **mof-drift v3 扩展**: 沿用 v2 模式 (排除自指, 触发条件)
- **gbrain 53 TODOs**: 不删任何代码, 仅分类 (P48 只做"识别", 不"实施")

## 验收标准

1. **G1** P48-GBR-AHEAD PLANNED task 创建
2. **G2-G3** mof-drift 报告含 gbrain ahead 数量 + todo 4 类分类
3. **G4-G5** 17 项目 0 lint
4. **G6** omo governance ≥ 100 A+
5. **G7-G9** task done + mof-version v0.0.36 + 收口报告

## 风险

| 风险 | 缓解 |
|------|------|
| gbrain 子仓 ahead 推送触发 CI 悬空 | 不在 P48 推, 仅识别 (P49+ 推) |
| 53 TODOs 误分类 | 4 类仅 "识别", human review 后续处理 |
| mof-drift 误报 | 排除自指 + 沿用 v2 模式 |

## 关联

- P47 R3 (mof-drift v2 + stale_planned_tools)
- P44 DEFER-SUBMODULE-PUSH (gbrain 15 commits)
- P44 DEFER-GBRAIN-OPERATIONS-TS (已 2026-06-20 完成)

## NoGos (YAGNI)

- ❌ 不删任何 gbrain TODO
- ❌ 不实施 53 TODOs (P49+)
- ❌ 不推送 gbrain 子仓 (P49+)
- ❌ 不改 mof-drift 现有 4 维度逻辑
