---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-24
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0225-g-del-physical-multihost-gate-caliber.md
  - 0226-g-del-1-blocked-until-four-hosts.md
  - STRAT-P80-strategic-roadmap.md
  - STRAT-P81-strategic-roadmap.md
supersedes: []
amends: []
---

# ADR-0228: M1 收敛期验收通过 + 物理底座挂起下的兑现期推进顺序

> **编号**: `next-adr-id.py --session m1-acceptance --claim` → **0228**。
> 两项人类决策同日落档（2026-07-24, 夏明星口头批准, 会话记录为凭）。

## Context

1. STRAT-P81 S0.1 已将 M1 验收申请卡送 BRIEF Inbox（`needs-human-p81-m1-acceptance`）。
   三门禁 evidence: daemon 在线率 100% · 并发 agent 主仓冲突 0（claim 覆盖）·
   health 100/100 (ISC-3) 且 anomaly 清零（各值以 `.omo/state/system.yaml` 当日快照为凭, 指针化）。
2. S0.3 物理探测 fail-closed: `reachable_physical_hosts=1`（macmini/y7000p/tailscale 三路全不通,
   见 `audits/2026-07-24-p81-s0-physical-probe-failclosed.md`）。用户决定**暂挂机器修复**, 先推进其他工作。

## Decision

### D1 · M1 收敛期验收 **通过**（2026-07-24, 提前于原计划 2027Q1 约两个季度）

- ADR-0210 收敛期正式关闭, 兑现期启动。`needs-human-p81-m1-acceptance` 卡可关闭, 关闭理由引用本 ADR。
- 提前达标归因: 收敛纪律（Option B）执行到位, 记入战略复盘素材。

### D2 · 物理底座挂起, 兑现期按"非物理优先"重排（amends STRAT-P81 §1 解锁表）

| 工作面 | 原解锁条件 | 调整后 |
|--------|-----------|--------|
| S1 非物理项（注册中心/调度 harness 代码/故障转移设计） | M1 + S0 全绿 | **OPEN**（M1 已过; 本地与 sim 环境开发+测试, 只填 `meets_sim_harness`） |
| S1 物理 KPI（G-DEL.1 / G-DEL.3 官方达标） | 4 机 / ≥2 机真机 | **保持 BLOCKED**（ADR-0225/0226 不变, 待机器恢复） |
| S2 多角色（G-DEL.2b 为 process-local 口径, ADR-0225 允许） | G-DEL.3 达标 | **OPEN**（提前解锁; 角色框架不依赖多机） |
| S3 蜂群 | G-DEL.2b + kill-switch 评审 | 不变（LOCKED） |
| 纵贯线 A/B | 无 | 不变（OPEN） |

### D3 · 挂起项的看板义务

`needs-human-p80-physical-hosts` 卡**保留不关**, 每周治理巡检（纵贯线 B）在 BRIEF 重申一次,
防止挂起变遗忘。机器恢复后第一优先执行 S0.3 探测补测。

## Consequences

- 正面: 兑现期不因硬件停摆; G-DEL.2b（角色协作）与注册中心开发并行推进, 机器恢复后物理 KPI 直接套用已建成的 harness。
- 代价: S1 物理 KPI 达标时间不可预估, 依赖用户硬件修复; 蜂群叙事中「多机」一词在达标前不得对外宣称。
- 影响面: STRAT-P81 §1 解锁表（本 ADR 为其修正 SSOT）; execution brief 同步更新。

## Confirmation

- `adr-coverage.py` / `doc-ssot-lint.py` 通过
- execution brief §1 表与本 ADR D2 一致
- BRIEF Inbox: m1-acceptance 卡关闭引用本 ADR; physical-hosts 卡保留
