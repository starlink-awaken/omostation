---
status: PROPOSED
lifecycle: strategy
owner: 夏明星
last-reviewed: 2026-07-24
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0225-g-del-physical-multihost-gate-caliber.md
  - 0226-g-del-1-blocked-until-four-hosts.md
  - 0227-governance-ideal-architecture.md
  - STRAT-P79-strategic-roadmap.md
  - phase45-plan.md
supersedes: []
---

# STRAT-P80: 收敛期收尾 — M1 提前打绿 + 兑现期底座前置

> **For agentic workers**: 本文档为 **PROPOSED** 状态战略路线图，覆盖 2026-08 ~ 2026-10。
> 上位战略为 ADR-0210（收敛优先，三阶段）。**P80 精神**: 不加新图纸，把 M1（原定 2027Q1）
> 三条门禁提前打绿，同时把兑现期唯一硬前置（4 物理节点）并行凑齐，争取提前一个季度进入兑现期。
> 配套执行指令 → `.omo/plans/strat-p80-agent-execution-brief.md`。

## 0. TL;DR

| 字段 | 值 |
|------|-----|
| **决策 ID** | STRAT-P80-2026-07-24 |
| **基线** | health 84 (ISC-3) · GAC anomaly 45 · daemon 100% · debts 7/7 resolved · physical_hosts 2 |
| **总预算** | 8-10 周 · 4 条战线 |
| **首推动作** | 战线 1: GAC anomaly 45 专项归因 + Phase 45 Wave 1 |
| **总目标** | M1 三门禁全绿 · reachable_physical_hosts ≥ 4 · KOS 在轨 · X3 工作交付月度软门禁 |

## 1. 基线与判断

### 1.1 现状快照（2026-07-24, 指针化 — 勿手抄传播）

- 复合健康分: 84（源 `.omo/state/system.yaml::health_score`, ISC-3 口径）
- GAC 异常扣分: 45（**当前唯一战略级红灯**）
- daemon 在线率: 100%（M1 门禁一已达标）
- Phase 44 七项债务: 全部解决; ADR-0227 四原则 10 PR 全落地
- 物理节点: `reachable_physical_hosts=2`（local-mac + macmini）< 4（G-DEL.1 BLOCKED, ADR-0226）
- KOS: 3231 篇（Q4 底线 3000 已过, 下一目标 2027Q1 ≥ 5000）
- X3 价值: 创意创作 661 vs 工作交付 4 卡片（失衡信号）

### 1.2 战略判断

M1 三条验收中两条实质达标或接近达标，唯一红灯是 health/anomaly。四原则闭环刚建成，
第一批被"诚实化"暴露的异常正在涌出——这是设计预期而非退化，但必须在本期消化。
兑现期的唯一硬前置（4 物理节点）不受"收敛期只治本"约束，应并行推进。

## 2. 四条战线

### 战线 1 (P0) · 收敛期收尾 — M1 提前打绿（Week 1-6）

| 交付 | 价值 |
|------|------|
| GAC anomaly 45 专项归因（真实异常 vs 新口径误报分类处置） | 解锁 M1 门禁三 |
| Phase 45 W1: 健康自检 + tick 超时 + debt auto-seed | 治理自维护 |
| Phase 45 W2: agora-gateway HTTP /health + debt_adjusted 实时化 | 可观测 |
| Phase 45 W3: 472 task 熵清理 + BOS transport 试点 3 服务 | 熵收敛 |
| STRAT-P79 收尾: health→95+ · GaC 173 冻结声明 · Foundry 运营 SOP | P79 闭环 |

### 战线 2 (P0, 与战线 1 并行) · 物理底座扩容 — 解锁兑现期（Week 1-8）

| 交付 | 价值 |
|------|------|
| y7000p SSH 接入 + 云节点评估, `reachable_physical_hosts` 2→≥4 | 解除 G-DEL.1 BLOCKED |
| G-DEL.3 跨机同步 2 机真机达标（ADR-0226 允许 ≥2） | 兑现期首个物理验证点 |
| 多机健康探测纳入 runtime 健康扫描 | 底座可观测 |

### 战线 3 (P1, 季度节奏) · KOS 跃迁期前置积累

| 交付 | 价值 |
|------|------|
| KOS-Q-GROWTH 保持在轨: 3231 → 2027Q1 ≥ 5000 | 个人大脑数据地基 |
| 季度测量写回 goals/current.yaml（evidence 留痕） | 度量诚实 |

### 战线 4 (P1) · X3 价值产出软门禁

| 交付 | 价值 |
|------|------|
| 月度工作交付卡片软门禁（建议 ≥ 8 张/月, 具体数值人类拍板） | 防"治理自嗨" |
| BRIEF X3 仪表增加月度环比 | 失衡可见 |

## 3. 门禁与冻结区

- **M1 提前验收条件**（全绿即可申请提前进入兑现期, 需人类拍板）:
  daemon ≥ 90% · 并发 agent 主仓冲突 = 0（claim 覆盖率 100%）· health ≥ 95 且 GAC anomaly ≤ 10
- 收敛期内**禁止启动** VISION-ROADMAP Phase 2-5 的新功能建设（硬件扩容与 G-DEL.3 除外, ADR-0226 §Consequences）
- health < 95 时禁止新增 GaC 规则（承接 P79 冻结区）
- G-DEL.1 严禁以 2 机或 sim 冒充达标（fail-closed, ADR-0226）

## 4. 风险

| 风险 | 缓解 |
|------|------|
| GAC anomaly 归因发现深层结构性问题 | 按 ADR-0227 治本方法论处理, 不打补丁 |
| 硬件扩容交期不可控 | 不阻塞战线 1/3/4; G-DEL.3 先以 2 机达标 |
| 收敛纪律被愿景叙事挤占 | 本 STRAT 冻结区 + phase-gate-check CI |

## 5. 相关

- 上位: ADR-0210（三年三阶段, ACCEPTED）· `docs/STRATEGY-3YEAR-PANORAMA.md`
- 承接: STRAT-P79（2026-07-08 ~ 08-30, 与本 STRAT 战线 1 交接）
- 执行: `.omo/plans/phase45-plan.md` · `.omo/plans/strat-p80-agent-execution-brief.md`
- 本 STRAT 覆盖: 2026-07-24 ~ 2026-10-15
