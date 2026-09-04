---
id: ADR-0414
title: ADR-0247 与 ADR-0225/0226 物理多机张力 — 关系澄清
status: archived
lifecycle: spec
owner: governance-team
created: 2026-08-17
last_updated: 2026-08-18
deciders:
  - 夏明星 (最终确认 pending)
  - governance-agent (起草)
related:
  - .omo/_knowledge/decisions/0225-g-del-physical-multihost-gate-caliber.md
  - .omo/_knowledge/decisions/0226-g-del-1-blocked-until-four-hosts.md
  - .omo/_knowledge/decisions/0247-strategic-pivot-collab-first-physical-deferred.md
supersedes: []
amends:
  - 0225-g-del-physical-multihost-gate-caliber.md
  - 0226-g-del-1-blocked-until-four-hosts.md
session: strategy-convergence-r3
---

# ADR-0414: 物理多机张力 — 0247 与 0225/0226 的关系澄清

## 状态

**ACCEPTED** — 2026-08-17 夏明星会话批准（"ABCE 都批准"，方案 a）。

## 张力陈述（事实）

| ADR | 日期 | 内容 | 冲突点 |
|---|---|---|---|
| ADR-0225 | 2026-07-19 | G-DEL.1/3 官方 caliber = 物理多机, fail-closed | 定验收硬标准 |
| ADR-0226 | 2026-07-19 | G-DEL.1 BLOCKED until 4 hosts (现 2<4) | 同上 |
| ADR-0247 | 2026-07-26 | 战略转向: 多 Agent 协作优先, **物理多机 deferred** | 投入优先级转向 |

三方互引为零（实测 0225/0226 中 grep '0247' = 0 次）。G-DEL.1 至今 BLOCKED
（reachable_physical_hosts=2 < min=4, phase-scope.yaml 实测）。

## WHY

悬而不决的张力让后续 agent 无法判断：G-DEL.1 的 fail-closed 是"必须现在
补机器"还是"等 deferred 解除"？期间任何 CI/巡检看到 BLOCKED 都可能触发
无意义的修复尝试或告警噪音。

## WHAT（决策：方案 a）

**物理多机 caliber 随 ADR-0247 一并 deferred。G-DEL.1 在 deferred 期间的
处理方式明确定义：**

1. **caliber 不降**：ADR-0225 的"物理多机是官方 caliber"判断保留 — deferred
   是资源/时机问题，不是标准错误。恢复时无需重新论证 caliber。
2. **fail-closed 语义降级为 parked**：deferred 期间 G-DEL.1 状态从
   `BLOCKED`（暗示待修复）改为 `PARKED-DEFERRED`（明确无动作项）：
   - 不产生告警、不进周报待办、不触发 agent 修复尝试
   - unblock_when 不变（≥4 reachable physical hosts AND physical measure）
3. **触发条件**：ADR-0247 的 deferred 解除（即多 Agent 协作线产出稳定）或
   四机硬件到位，二者取先。届时 G-DEL.1 自动回到 BLOCKED 语义排队。
4. **验收标准不被"多 Agent 优先"稀释**（0247 的优先级语义 ≠ 降低 0225 的
   验收严格度 — 这是本 ADR 对指令模板中方案 b 的否定理由：方案 b 的
   "caliber 不受影响"表述会让 PARKED 缺乏依据，两方案实质差异仅在
   deferred 期间的状态语义，方案 a 更诚实）。

## CONSEQUENCES

- `phase-scope.yaml` G-DEL.1 状态字段需同步改 `PARKED-DEFERRED`（本轮附带）
- 0225/0226/0247 的 `related:` 回填指向本 ADR（done_when 要求）
- 若人类选方案 b：本 ADR 的 §2 改为"保持 BLOCKED + 附加注记"，其余不变

## REJECTED ALTERNATIVES

- **方案 b（caliber 不受 0247 影响，仅澄清优先级）**：G-DEL.1 继续 BLOCKED
  展示，deferred 期间持续产生"为何 BLOCKED 无人修"的认知成本。
- **正式废除物理多机 caliber**：过度反应 — 硬件到位后物理多机验证仍是
  分布式一致性的金标准，且 ADR-0225 的风险分析仍然成立。
