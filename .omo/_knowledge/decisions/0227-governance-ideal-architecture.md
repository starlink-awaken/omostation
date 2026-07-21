---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-21
related:
  - 0220-swarm-coordination-discipline-m1-gate.md
  - 0218-agent-isolation-p0-verify-and-hygiene.md
  - ../patterns/p73-truth-driven-engineering-pattern.md
supersedes: []
---

# ADR-0227: 治理架构理想态 — 4 原则 (分层/单源/自审/闭环)

> 九轮深挖诊断 (2026-07-19 → 07-21) + 10 PR 落地. 从 "GHA 连挂8天零告警 + health N口径 + 回路断链" 到 4 原则全闭环.

## Context and Problem Statement

2026-07-19 起 c2g-radar-daily GHA 连挂 8 天零告警, 暴露 omostation 健康治理体系多重系统性病:

- **schedule automation 普遍撞分支保护**: c2g-radar / c2g-gc-weekly / audit-rollout-monthly 的 bot push main 被 `required_pull_request_reviews + enforce_admins` 拒 (GH006). health.yaml/decayed/audit-metrics 的 main commit 全是手动 PR merge, **bot push 从没成功过**.
- **ghost 检测自指死循环**: CR-X2-GAC-EXEC-DRIFT executor = `radar_cron` = compass-radar (被检测对象自己). 连挂时检测器也 ghost → 永远检不到.
- **健康分 N 口径打架**: ISC-1/2/3 三版本并存 + 10 生产者, 58/70/83/88 四个值同框.
- **回路断链**: `state_stale` emit 671 条零消费者 (死回路, emit 没人看).
- **运行时快照污染 main**: health.yaml / decayed pitches / audit-rollout 走 bot commit main.

九轮诊断反复翻案 (每轮"终局"是下轮偏见), 最终收敛到 4 条架构原则.

## Decision Drivers

- **D1 修一层暴露下一层**: yaml 修好暴露分支保护, 分支保护修好暴露自指 → 要架构层治本, 非补丁堆叠 (slop).
- **D2 已有机制大面积休眠**: GaC 192 rule, `ci_gate/omo_audit` 接 165/140, 但 `radar_cron(25)/evidence_smoke(2)` 低频真空. 声明面丰富, 执行面滞后.
- **D3 decl-exec-gap 标志性反 pattern**: 声明面 SSOT 漂亮, 执行面没接 (omostation 反复踩).

## Considered Options

- **A 继续修回路 (接 probe/gate)**: 治标, 回路修不完, 补丁堆叠 (slop).
- **B 砍合成分**: 破坏 cockpit 9 处业务文案依赖 (`health_score<90` 触发 Builder 提示), 重构地震.
- **C 4 原则归位 + 接线 (选定)**: 现有架构严格化, 复用 GaC/write-owners/services.yaml, 非推倒重建.

## Decision Outcome: 4 原则

### 原则1 · 分层不越界 (运行时快照永不进 main)

```
L0 协议  GaC registry / services.yaml / write-owners     ← SSOT, 只读, PR 维护
L1 运行时 health.yaml / system_health.yaml / decayed / _delivery  ← gitignored, daemon/cron 产
L2 内核   compass_radar (唯一 health writer) / evidence-smoke
L3 入口   cockpit reader adapter
L4 文档   BRIEF (指针引用 L1, 不复制值)
```
派生层绝不反向写 SSOT. **落地**: #440 c2g-radar 去 Commit step + foundry 5:52 / #443 c2g-gc / #444 audit-rollout.

### 原则2 · 单源硬阻断 (一个 writer + N reader adapter)

每字段**唯一 writer** (write-owners 硬阻断, 无 CI 豁免), N reader 走**统一 adapter** (不自算口径). 治 N 口径打架 + 孤儿字段. **落地**: #442 CR-X4-HEALTH-SSOT 去 `--warn-only` 升硬阻断 + BRIEF ISC-1→ISC-3.

### 原则3 · 自审独立 (审计器 ≠ 被审对象)

ghost/health 审计由**独立层** (foundry cron 本地 launchd + evidence-smoke GHA) 跑, 多源交叉, 不依赖被审对象. 破自指死循环. **落地**: #439 ghost 检测代码 + foundry 5:55 deck / #441 CR-X2-GAC-EXEC-DRIFT + CR-X1-EVIDENCE-RUNNABLE executor → `foundry_cron`.

### 原则4 · 闭环回路 (emit → 检测 → 触达 → 决策)

每个 emit 必须有消费者 (lint 强制), 消费者产出告警进 **BRIEF Decision Inbox** (人能看到), 触达通道 (slack/macOS). 治死回路. **落地**: #445 event-loop-lint 检测死回路 + foundry 5:57 deck / #446 `--alert` 写 needs-human 卡片进 BRIEF Inbox.

## Consequences

- **正面**: 4 原则全闭环; schedule automation 通病系统性治本 (4 workflow); 破自指死循环; 死回路真能触达人.
- **代价**: health.yaml tracked 过渡态 (P2 gitignore 留 — check_health_ssot CI fallback 改是 slop, 且 #440 已实质"不污染 main", gitignore 收益小风险中).
- **影响面**: 治理面 (GaC/services/write-foundry cron), 不改业务逻辑.
- **后续**: 单源 reader adapter (compass_radar 唯一 writer, 9 reader 改 adapter) / gac-coverage-lint (声明即执行) / health_alert 主动通知 (slack/macOS).

## Confirmation

- 4 原则全落地 (10 PR #437-#446 merged, GitHub main HEAD=`cbe0b9a32`).
- c2g-radar `workflow_dispatch` 验证 `conclusion: success` (8 天连挂终结).
- event-loop-lint 主仓验证检测 `state_stale 671 死回路` + 写 needs-human 卡片 ✓.
- foundry cron 5:52/5:55/5:57/6:00 闭环链 (明天 daily 自然验证).

## 治本方法论 (九轮沉淀的 3 纪律)

1. **追全链路** (emit≠告警, 追到执行器真跑/人能看到).
2. **先查三表** (GaC registry/write-owners/services, 90% 休眠非缺失).
3. **系统性必量化** (executor 覆盖率附数字, 不凭采样下全局).

---

*ADR-0227 · ACCEPTED · 2026-07-21 · 夏明星 · 治理架构理想态 4 原则 + 10 PR 落地*
