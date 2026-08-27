---
status: PROPOSED
lifecycle: strategy
owner: 夏明星
last-reviewed: 2026-07-24
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0225-g-del-physical-multihost-gate-caliber.md
  - 0226-g-del-1-blocked-until-four-hosts.md
  - STRAT-P80-strategic-roadmap.md
supersedes: []
---

# STRAT-P81: 兑现期启动 — 蜂群从图纸到真机 (2026-08 ~ 2027-06)

> **For agentic workers**: 本文档为 **PROPOSED** 状态长期路线图，是 ADR-0210 三年战略
> **第二阶段（兑现期）**的执行分解。上接 STRAT-P80（收敛期收尾，M1 三门禁 2026-07-24 已形式全绿）。
> **P81 精神**: 收敛期证明了"系统对自己诚实"；兑现期要证明"愿景能在真机上跑通"。
> 每一步以**物理执行面门禁**验收（ADR-0225/0226 fail-closed 口径），严禁模拟冒充。
> 配套执行指令 → `.omo/plans/strat-p81-agent-execution-brief.md`。

## 0. TL;DR

| 字段 | 值 |
|------|-----|
| **决策 ID** | STRAT-P81-2026-07-24 |
| **基线** | health 98 · M1 三门禁形式全绿 · physical_hosts 待重测（macmini 修复中, macbook 已注册）· KOS 3231+ |
| **总跨度** | 11 个月 · Stage 0-3 + 两条纵贯线 |
| **首推动作** | Stage 0: M1 提前验收申请 + P80 残留清偿 |
| **总目标** | G-DEL.1/2b/3/5b 真机达标 → 蜂群多机/多角色/涌现初步兑现, 比原计划提前约 2 个季度 |

## 1. 战略判断

1. **M1 提前于原计划（2027Q1）约两个季度形式达标**——收敛纪律赢得了时间。兑现期可提前启动，
   但入场券必须走正式验收（evidence 汇总 + 人类拍板），不搞默认晋级。
2. **兑现期最大风险不是能力建设，而是假绿回潮**——分布式指标天然难测。全程沿用 fail-closed
   物理口径（ADR-0225/0226），G-DEL.1 严守 4 物理机，G-DEL.3 严守真机测量。
3. **收敛纪律不解除，改为常态运营**——GaC 冻结维持、软门禁运营、健康分 ≥95 红线，
   兑现期任何 Stage 中 health < 95 即暂停新建设转入修复（继承 P80 冻结区）。

## 2. 路线图

### Stage 0 · 入场与清欠 (2026-08, ~3 周)

| 交付 | 门禁/验收 |
|------|-----------|
| M1 提前验收申请卡（evidence 汇总 → BRIEF Inbox → 人类拍板） | 拍板通过 = 正式进入兑现期 |
| P80 残留 4 卡清偿: tick-timeout / agora :9000 health / task 熵 477→<200 / bos_stdio 69.2%→<65% | phase45 七 endpoint 全绿 |
| 物理底座重测: macmini 修复 + y7000p + macbook(tailscale) 4 机探测 | `reachable_physical_hosts ≥ 4`（脚本探测, 禁手填） |
| 全节点 Tailscale 化（endpoint 抗漂移） | 探测脚本改用 tailnet 地址, DHCP 漂移不再致失联 |

### Stage 1 · 多机协作真机化 (2026-09 ~ 2026-12)

对应 VISION-ROADMAP Phase 2。**先 2 机真达标，再 4 机扩展**。

| 交付 | 门禁/验收 |
|------|-----------|
| G-DEL.3 跨机状态同步: 2 机真机 → 4 机 | sync p99 < 100ms, `env_class=physical_multi_host` |
| Agent 注册中心（runtime+agora, 节点/角色/能力注册与发现） | 4 节点自动注册+心跳, 假死可检出 |
| 分布式任务调度: 真机 harness 常态化跑批 | **G-DEL.1: 4 机 schedule success > 99%**（解除 BLOCKED 后测） |
| 故障转移: 单节点拔线演练 | 任务不丢, 自动迁移, 演练报告入 audits |
| 多机健康纳入 compass/BRIEF（节点在线率进健康分口径） | BRIEF 展示节点矩阵 |

### Stage 2 · 多角色协作 (2027-01 ~ 2027-03)

对应 VISION-ROADMAP Phase 3。

| 交付 | 门禁/验收 |
|------|-----------|
| 角色定义框架 + 协作协议（aetherforge/swarm + metaos） | 3 角色真实任务协作 |
| **G-DEL.2b: 3 角色协作任务完成率 > 95%**（process-local 可验收） | 官方 meets_gate |
| 角色记忆共享（gbrain 跨任务上下文, 承接 W3 资产） | 角色间上下文可检索、有隔离边界 |
| 角色评估: 每角色完成率/成本进 X3 仪表 | BRIEF 可见 |

### Stage 3 · 蜂群智能初步 + 安全闸 (2027-04 ~ 2027-06)

对应 VISION-ROADMAP Phase 4 前半。**涌现类能力安全优先**（承接 ADR-0221 风险评审）。

| 交付 | 门禁/验收 |
|------|-----------|
| 涌现行为检测器 | **G-DEL.5b: 检测准确率 > 80% + kill-switch 演练通过** |
| 集体决策机制（有限范围: 任务分派/优先级投票） | 决策可追溯、人类可否决 |
| 蜂群可视化（cockpit 节点/角色/任务流面板） | 面板与 SSOT 一致 |

### 纵贯线 A · 个人大脑数据积累（跃迁期前置, 全程）

| 节点 | 目标 |
|------|------|
| 2026Q4 | KOS ≥ 3000 已达, 保持增量 + 质量抽检 |
| 2027Q1 | **KOS ≥ 5000**（KOS-Q-GROWTH 既定 floor） |
| 2027Q2 | 个人知识图谱 PoC: KOS × gbrain 打通一条真实查询链路 |

### 纵贯线 B · 治理常态运营（全程）

| 机制 | 节奏 |
|------|------|
| foundry cron 闭环链 + compliance 巡检 | daily / weekly |
| X3 工作交付软门禁 | 月度, 阈值人类年检 |
| 战略复盘（本 STRAT 对照实际） | 每 Stage 收尾 + 季度, 偏差 >1 个月立 amend ADR |
| GaC 冻结维持（health ≥ 95 才可增规则） | 常态 |

## 3. 门禁与红线（全程有效）

- 兑现期入场必须经 M1 正式拍板；Stage N 未过门禁不得启动 Stage N+1 的新建设
- G-DEL.1/3 官方达标仅认 `physical_multi_host` 真机测量（ADR-0225/0226, fail-closed）
- health < 95 → 冻结当前 Stage 新建设, 转修复直至恢复
- 涌现/集体决策类能力必须先有 kill-switch 与人类否决通道, 后开真实流量
- KOS floor 未达季度目标时, 下季度纵贯线 A 升为 P0

## 4. 风险

| 风险 | 缓解 |
|------|------|
| 4 机底座交付不稳（家用设备睡眠/网络漂移） | 全节点 Tailscale + 不休眠基线 + 心跳告警进 BRIEF |
| 分布式建设诱发假绿回潮 | fail-closed 口径 + phase-gate-check CI 已在位 |
| 战线过长注意力分散 | Stage 门禁串行, 纵贯线仅两条, 其余一律不接 |
| 单人算力/精力瓶颈 | 每 Stage 预算内做减法优先于延期, 砍范围立 amend ADR |

## 5. 相关

- 上位: ADR-0210 三年战略 · `docs/STRATEGY-3YEAR-PANORAMA.md` · `docs/VISION-ROADMAP.md`
- 承接: STRAT-P80（收敛期收尾）· `.omo/plans/phase45-plan.md`（残留清偿）
- 执行: `.omo/plans/strat-p81-agent-execution-brief.md`
- 本 STRAT 覆盖: 2026-08-01 ~ 2027-06-30
