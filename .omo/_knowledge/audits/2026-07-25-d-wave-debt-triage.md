# D 波 — 小债清理去向 + KOS/X3 评估 (Round2)

> 日期: 2026-07-25
> workflow: 20260725T144239Z-governance-state-mutation-fd8784b8
> goal: strat-p81 round2 D 波

## D1 三债卡去向

| 卡 | 维度 | 去向 | 决策点 |
|----|------|------|--------|
| OPC-P6-SELF-EVOLUTION-doc-gate-e | self-evolution | **保留 planned 等 human approval** | self-evolution 红线"永不入 active 除非 human approval"; `approval_state=awaiting_human`; **不自决** |
| cockpit-debt-debt-1 | unknown | **送 Inbox 需 cockpit 分类** | `dimension=unknown`, `owner=unassigned`; 需 cockpit debt ledger 分类影响范围/责任人; `human_approval_required=false` 但分类需 cockpit 团队 |
| needs-human-p80-phase45-bos-stdio | P80 残留 | **保留等迁移窗口** | `bos_stdio_ratio ~69.2%` > 65% 阈值; REAL migration ~8 服务; **非"小债"**, 等迁移窗口 |

**结论**: 三卡去向明确, 不再无主漂. 无一卡可"一次修"——都需决策 (approval/分类/migration).
**红线**: OPC-P6 self-evolution 须 human approval (§F), 严禁代批.

## D2 KOS 质量 (服务 C3)

- C3 gbrain 黑板与 KOS 检索命中率联动 (纵贯线 A)
- D2 范围: 抽检 ≥50 篇质量修复 + 命中率基线迭代 (仅既有源)
- **评估**: KOS 索引 11648 篇 (BRIEF). 抽检 50 篇质量修复是中等工程 (需 KOS 质量管线).
  本轮 C3 未启动 (gbrain 黑板深化待 W3 cockpit 集成后). D2 留 C3 联动时做.

## D3 X3 八月开局 + 治理周巡检

- 7 月已收官 (4 交付, `audits/2026-07-25-d2-x3-jul-settlement.md`)
- 8 月起把 C 波真实产出如实登记交付卡 (不凑数)
- **评估**: 8 月计数起步 (本日 2026-07-25, 8 月未到). C 波 PR (#514) 是 7 月产出.
  compliance + P74 + health 巡检: P74 warn_count=0, health 96, anomaly 85 (owner 集中度).
  8 月开局待 8/1 起登记.

## 后续 (Round2 剩余)

- C3 gbrain 黑板深化 (跨任务复用 case ≥3, W3 cockpit 集成后)
- C4 协作仪表进 BRIEF (含失败率, 复用 X3 管线)
- W3 C1 五角色正式实装 (cockpit 集成, 用户已拍板 go)
- abe091ce 清理 (人类决策, 释放 project-code-change 通道)
- 8/1 X3 八月开局登记
