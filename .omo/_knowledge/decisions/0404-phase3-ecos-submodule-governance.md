---
id: ADR-0404
lifecycle: spec
owner: '@Builder'
last_updated: '2026-08-09'
---

# ADR-0404 Phase 3 eCOS Submodule Federated Governance

## Context
随着多 Agent 并发参与 omostation 各个子模块（特别是 gbrain, cockpit 等高频热点区域）的开发，旧的治理盲区暴露无遗。Agent 会直接越界修改子模块并重置 `git submodule` 指针，导致其他 agent 的工作丢失，甚至破坏依赖图。
前期通过 ADR-0371 在 3 个子模块实现了初步的 PASW (Per-Agent Submodule Worktree) 物理隔离，但这还不够。
为解决上述问题，我们需要在 Phase 3 实施“全域多维联邦治理”。

## Decision
我们决定采用“三维联防”方案收敛子项目及孙项目治理，锚定 `agent-workflow.py` 编排中枢，并由 `git-shim` 兜底：

1. **物理隔离 (Global PASW)**: 将现有的 PASW 方案从局部的 3 个子模块推广到全局 `gac-worktree.sh claim` 逻辑中。所有声明 `claim` 的 agent 均会被分配专属的 Submodule Worktree，杜绝多 agent 在主树上互相重置指针。
2. **逻辑防冲突 (A2A Path Locks)**: 在 `agent-workflow.py claim` 和 `gac-worktree.sh` 流程中深度集成 Swarm Bus。当 Agent 跨模块修改文件前，必须进行路径级别锁定和碰撞检测。
3. **拓扑阻断 (Affected Graph CI)**: 依赖 `docs/layer-contract.yaml` 的依赖关系，计算当前变更的受影响下游。一旦修改了底层依赖（如 eCOS 核心或 MOF），CI 会级联触发所有被影响子项目的测试（Cascading Testing），防患于未然。
4. **统一门禁下沉**: 将 `pre-commit` 等 Git Hooks 及 `git-shim` 同步贯穿至各个子模块，所有修改必须遵循主项目级别的 ADR-0203 契约。

## Consequences
- 解决了相互重置及代码覆盖问题（通过 PASW 与 Swarm 锁）。
- 提升跨子项目协同的安全感，依赖图联动变更可即时熔断违规提交。
- 引入一定的性能开销（PASW init 及依赖树遍历）。
- `git-shim` 的拦截能力需适配更复杂的跨仓上下文（环境隔离要求提高）。
