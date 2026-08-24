---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-24
---

# resident 常驻体系与治理接线深度复盘

> BET-Y1Q3-T6-14 复盘报告

## 1. 目标与愿景
常驻 Agent 体系旨在打破传统的“一次性会话”模式，构建具备长期记忆、自治自愈能力和事件驱动响应能力的常驻节点（Resident Node）。愿景是通过完善的运行时环境（SGF/BOS）和治理接线，实现多 Agent 协同进化。

## 2. 场景与功能
- **守护者节点（Watcher）**：持续监控 CI/CD、门禁以及 `gac-local-gate`。
- **治理修剪节点（Pruner）**：负责过期状态清理、孤儿文档回收。
- **决策辅助节点（Advisor）**：在架构变更、PR Review 等关键链路插入元决策信号。
- **独立任务节点（Worker）**：执行具体的 BET 认领与提交，依赖 `platform-rebase` 和独立 clone 拓扑防冲突。

## 3. 用户旅程 (User Journey)
- 开发者可以通过 `cockpit decide` 将抽象意图注入到决策收件箱（Inbox），Agent 会异步响应。
- Agent 在执行中自动校验治理门禁，并通过 `agent-workflow.py` 与人类确认状态。
- 如果发生冲突，Agent 通过 fallback/escape 机制（如 `SWARM_ESCAPE_ID`）或者独立 Clone 自主隔离修复，最终实现人类仅需监督而不需微操。

## 4. 体验评估
目前在隔离度（T1-05 独立 clone 退役）、状态对齐（T10-10 三方口径对齐）上已经完成了初步闭环，大幅缓解了共享 checkout 带来的并发踩踏问题。但部分长期悬挂的 Zombie 锁、孤立进程回收仍偶发。

## 5. 长期运营与运维
运营不再是修补代码，而是维护治理契约（`document-governance.yaml`、`governance-checks.yaml`）。
未来的运维演进方向将是全托管的 Agent 虚拟机（如 omlxc），彻底脱离人类主机。

## 6. 防腐与约束接线
- **MOF / SGF**：提供了 Agent 与真实环境交互的隔离边界，防止失控的读写。
- **BOS URI**：统一的资源访问抽象，屏蔽底层物理路径。
- **GAC Gate**：通过强类型的 yaml schema 和 python AST 分析拦截危险动作。

## 7. 结论与下一步（T1 Follow-up）
虽然 resident 体系已具雏形，但 `platform-rebase` 独立 clone 的退役与销毁阶段，目前缺乏完整的 provenance（溯源）快照。
我们已经起草了 `docs/superpowers/specs/2026-08-24-platform-rebase-retirement-provenance-design.md`，接下来的 `BET-Y1Q3-T1-11` 将专项实施。
