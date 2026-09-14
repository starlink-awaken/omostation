---
id: ADR-0444
status: accepted
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-08-31
type: ssot
---

# ADR-0444: 自进化 Harness 异构生态收束

- **Status**: ACCEPTED
- **Date**: 2026-08-31
- **Authors**: xiamingxing, Sisyphus
- **BOS**: `bos://governance/harness/self-evolving/*`
- **关联**: ADR-0443（收敛平衡）、ADR-0424（防腐管道）、ADR-0389（gate-ROI）、ADR-0203/0204（工作流强制）、ADR-0396（Resident）
- **SSOT**: `.omo/_truth/registry/harness-policy.yaml`

## Context and Problem Statement

当前工作区已进入治理收敛期：18 项目、19 子模块、5+4+1+1 层、288 BOS 服务、136 条 GaC、4 套控制面（local/CI/runtime/human）各自为政。`T1-13` 实战暴露 3 个病：`pre-push 22s` 串行无缓存、`ledger 追加` 天然冲突（411 文件 merge）、`bet-retro-due` 17 个存量债卡死增量 PR（靠 `SWARM_ESCAPE_ID` 逃生）。门越多，越像没有门。

未来 7 类变更（架构升级/功能/缺陷/体验/文档治理/工具链/业务流程）需围绕 `全景愿景-目标-身份-角色` 自进化，要求**常驻感知 → 事件标准化 → Harness 调度 → 白盒审计 → 复盘再进化**的闭环，而非散点拦截。

## Decision Drivers

* 异构必须编排而非同构化（Python/TS/Go + Docker/k8s/launchd + 本地/云/边缘）
* 规范已膨胀（21% 提交为 `arch`），需从文档变为可执行 Policy
* 存量债不能卡增量，`blocking/advisory` 必须分层
* 自进化需事件驱动，而非人肉 `start`

## Considered Options

1. **独立 Harness Controller**：新建 `bin/harness` + `harness-policy.yaml`，`agent-workflow` 收敛为马甲，`COMP-WS-omo` 为唯一 S
2. **原地增强**：在 `agent-workflow.py` 上打补丁，`gac` 各跑各的
3. **重写 GaC 引擎**：Go/Rust 重写 `bin/gac/*`，废弃现有

## Decision Outcome

**Chosen option: "独立 Harness Controller（薄） + 厚复用"，因为现有 `bin/gac/*`、`bus-foundation`、`agora` 已成熟，重写成本 > 收束收益。**

### Consequences

* Good: 单入口 `harness run`，`Policy Registry` 单一事实源，`pre-push 22s→5s`，`PR 冲突率 70%→10%`，`SWARM_ESCAPE <5%`
* Bad: 需一次性把 136 GaC + X1-X4 + MOF + 12 维度 + 5 阶段价值循环全量声明进 `harness-policy.yaml`（218 行，已完成）

### Confirmation

* `harness trace <run-id>` 一行回放 `admission→audit`
* `make architecture-check` 全绿
* `python3 bin/plan/bet-ledger.py lint` OK

## Pros and Cons of the Options

### 独立 Harness

Pros: 单 S，DAG 并行，缓存，可观测
Cons: 需新建 `harness-policy.yaml`

### 原地增强

Pros: 零新文件
Cons: `agent-workflow.py` 膨胀至 4000 行，Policy 再次分裂

## References

* `.omo/_truth/registry/harness-policy.yaml`
* `docs/project-registry.yaml` + `ARCHITECTURE.md`
* `T1-13 PR #2817` 实战复盘
