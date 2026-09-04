---
lifecycle: history
owner: governance-team
last_updated: "2026-07-29"
---
# X4: 综合 D1-D6 执行 (integrated-governance-master-workorder §D)

> 上位: V4 解决 (人类定位) + X4 派发
> 来源: `.omo/plans/integrated-governance-master-workorder.md` §D (107-118 行)
> 🔴 例外二核对 (用户已做): 六项**没有一项结论依赖"协作普遍正收益"**, 全部按推荐执行

## 综合 D1-D6 决策 + 例外二核对

| # | 决策 | 定 | 例外二核对 (依赖协作普遍正收益?) | 执行 |
|---|------|---|-------------------------------|------|
| D1 | model-driven CLI | B 先切 cockpit adapter 再删 | ❌ 技术决策 (CLI 迁移) | 按推荐 |
| D2 | gbrain 三栈拆分 | B 冻结 | 🟡 沾边 (原理由 ADR-0237 黑板), 但协作收窄后黑板更重要性降, **冻结更稳** | 按推荐 + **理由更新** |
| D3 | omo vs omo-debt | A + 6 周评估 | ❌ 边界澄清 | 按推荐 |
| D4 | family-hub | A L2 dormant | ❌ 项目状态 | 按推荐 |
| D5 | kairon root e2e | A 先试 2 周 | ❌ 测试工程 | 按推荐 |
| D6 | 存量跨层违规 | B 分批 6+6 | ❌ 违规治理 | 按推荐 |

**例外二结论** (用户核对): 六项**全部不依赖协作普遍正收益**, 按推荐执行.

## D2 理由更新 (X4 要求)

**原理由**: "ADR-0237 黑板未关不宜大拆"
**新理由** (协作适用面收窄后): **"协作适用面收窄 (R1: 思考性任务协作 0.5-0.6x), 黑板重要性下降, gbrain 冻结更稳"**

依据:
- R1 纯 text: 思考性任务协作 0.5-0.6x (单 agent 优)
- D2 (human-delegated): 协作仅"简单独立批量"
- 黑板 (协作记忆) 在协作适用面收窄后, 重要性下降
- → gbrain 三栈拆分冻结 (不拆) 更稳 (避免拆了又因协作收窄而闲置)

**结论不变** (B 冻结), 理由更新.

## 执行状态

- D1-D6: 按各工单已载推荐执行 (decision-checklist 大部分 closed 2026-07-28)
- D2 理由: 待落档 (gbrain 工单 / ADR-0237 amend, agent 不擅自改 ADR, 标注待人类)
- 例外二: 用户已核对 (六项不依赖协作前提, 不退回)

## 🔴 红线
- 例外二不自行判定"不适用" (用户已核对六项)
- D2 理由更新落档 (不擅自改 ADR, 走流程)
- 综合 D1-D6 按推荐 (不因协作收窄而推翻技术决策)

## References
- V4 (人类定位综合 D1-D6 出自 integrated-governance-master-workorder §D)
- R1 纯 text (协作收窄) · D2 (适用面)
- decision-checklist-13-items.md (D1-D4 closed)
