---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: OMOStation 90% 成熟度与机器自治自愈总纲 (Phase 4)
type: doc
---

# OMOStation 90% 成熟度与机器自治自愈总纲 (Phase 4)

## 1. 北极星愿景：90% 机器自治自愈率

在 Phase 4 中，系统的终极成熟度指标并非“测试覆盖率”或“文档完整度”，而是**机器自治自愈率 (Autonomous Recovery Rate)**。

**定义**：
当系统发生 100 次预期外漂移（如文档滞后、配置损坏、守护进程宕机、子模块引用断裂）时，必须有 ≥90 次由后台 Resident Daemon 或 Agent Swarm 自行察觉，并通过 A2A 总线自动发起诊断、生成修复 PR，甚至直接实施热修复，全过程**无需人类介入 Terminal**。

## 2. 核心量化公式

$$
\text{Autonomous Recovery Rate} = \frac{\text{Auto-Remediated Drifts} + \text{Auto-Repaired Failures}}{\text{Total Drifts} + \text{Total Failures}} \ge 90\%
$$

## 3. 支撑此愿景的三大支柱 (Phase 4 战术)

### 3.1 脚本 444 全登记 (Script Registry Strict Enforcement)
所有散落的游离脚本必须统一进入 `.omo/_truth/registry/governance-scripts.yaml`。幽灵脚本是机器自愈的盲区。任何未登记的脚本若导致问题，系统无法定位责任 Domain，因此第一步是**账本对齐**。

### 3.2 独立 Clone 退役与单干心智统一
物理层面上退役 `~/agents/` 目录下的多重 Clone。既然我们在 Phase 3 构建了 AST Semantic Blackboard（语义黑板），Agent 防冲撞应升级为**内存级语义锁**，而不是浪费 IO 和 CI 算力的物理 Worktree 隔离。物理拓扑的极简是实现高阶自动化的前提。

### 3.3 Resident 常驻守护体系闭环
将 `omlxcd` (0ms TTFT 算力)、`B.D.S.K Cell` (四角虚拟董事会)、`omo daemon` 等常驻进程的生命周期，从“人类 Makefile 手动拉起”转变为“K8s 般的自愈重启”。

## 4. 演进路线图 (Phase 1 ~ Phase 5)

* **Phase 1-2**: 止血与防腐，构建因果黑板。*(已完成)*
* **Phase 3**: 引入 A2A 协商总线与 B.D.S.K 虚拟董事会，实现多 Agent 认知对齐。*(已完成)*
* **Phase 4**: **全域成熟度覆盖与自动化收敛**。执行脚本 444 全登记、独立 Clone 退役，拔除物理债，推高自愈基线至 90%。*(当前阶段)*
* **Phase 5**: 意图级端到端履约 (Intent-to-Execution DAG) 与 Sovereign Health 数据主权沙盒的全面合规。

---
> 目标达成后：score_iterable 分数将由 6 跃升至 8。
