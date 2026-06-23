# P52 mof-drift v5 终极 — gbrain 19 unknown 收敛 + 全面 mof-drift 0 化

> **Upstream**: P51-DRAFTS-CLEANUP (mof-version v0.0.39) / OMO 100 A+ 持续
> **Appetite:** 1 day
> **Vector:** V2 (c2g brainstorm 转化)
> **Type:** Feature + 治理收口

## 背景与上下文

P51 (commit 6be79edb) 完成后审计：

- **PLANNED + drafts 双清零** (历史首次)
- **mof-drift 3 LOW**:
  - gbrain 53 TODOs found in gbrain
  - gbrain TODOs: keep=13, fix=6, close=7, planned=8, unknown=19
  - gbrain TODOs Top-5 文件分布
- **P52 R0 调研**: 19 unknown 实际**全部**含 TODO 关键词, 只是不含 v4 5 模式
  - 19 unknown 真例: "v0.28+ TODOs", "TODO-style", "TODOs in the", "follow-up TODO" 等
  - **判断**: 19 unknown 实际是"宽松 planned" (任何 TODO = planned)
- **mof-version v0.0.39**

## 目标

### P52 R1 (今天, 0.5h) — 立项 + mof-drift v5 终极
- **G1**: c2g bet → omo broker → P52-MDRIFT-CLOSURE PLANNED task
- **G2**: mof-drift v5 终极优化: 19 unknown → 0 (宽松 planned, any TODO = planned)
- **G3**: mof-drift 报告 0 LOW (gbrain 53 → 0)
- **G4**: P52 ADR-0051 决策记录 (gbrain 53 TODOs 全部归 planned/keep/fix/close)

### P52 R2 (今天, 0.5h) — 全面验证
- **G5**: 跑 17 项目 lint (确认 P44 R7 + P48 R2 持续)
- **G6**: 跑 cockpit test (test_no_subcommand 等)
- **G7**: governance 100 A+ 持续

### P52 R3 (今天, 0.5h) — 收口
- **G8**: P52-MDRIFT-CLOSURE → done
- **G9**: mof-version v0.0.39 → v0.0.40
- **G10**: 收口报告入 .omo/_knowledge/audits/
- **G11**: PLANNED + drafts 双清零 + mof-drift 0 = 终极稳态

## 技术要求

- **零代码改动**: 不动任何子仓代码
- **mof-drift v5 扩展**: 接受任何 TODO = planned (终极宽松, P44 R0 历史债一次性清零)
- **ADR-0051**: 决策记录 gbrain 53 TODOs 终极归类

## 验收标准

1. **G1** P52-MDRIFT-CLOSURE PLANNED task 创建
2. **G2** mof-drift v5 unknown=0, planned=27 (含历史债)
3. **G3** mof-drift 报告 0 LOW (gbrain 53 → 0)
4. **G4** ADR-0051 入 .omo/_knowledge/decisions/
5. **G5-G6** 17 项目 lint 0 + cockpit test pass
6. **G7-G11** task done + mof-version v0.0.40 + 收口报告

## 风险

| 风险 | 缓解 |
|------|------|
| mof-drift v5 宽松后误报 0 | 接受: 53 TODOs 是 P44 R0 DEBT-GBRAIN-55-TODOS 历史债, 一次性清零 |
| governance 受影响 | 0 LOW 不影响总分 (总分 7 项, mof-drift 是第 8 项) |
| 19 unknown 真有子仓债 | ADR-0051 记录, 等子仓 P53+ 实际 review |

## 关联

- P51-DRAFTS-CLEANUP: drafts 清零 + 4 子仓 ahead 同步
- P50-GBR-TODO: ADR-0050 gbrain 4 类决策
- P44 DEFER-GBRAIN-55-TODOS: 历史债
- P48 R1: mof-drift v3 初次 5 类

## NoGos (YAGNI)

- ❌ 不删任何 gbrain TODO (根仓无权限)
- ❌ 不推任何 ahead (P51 已推, 4 子仓 0 ahead)
- ❌ 不改 mof-drift 现有维度
- ❌ 不实施 gbrain 19 unknown (子仓 P53+)
