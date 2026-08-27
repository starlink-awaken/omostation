---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Legacy 项目融合方案

> 基于 AGENTS.md 架构治理与全架构分析 v3.0
> 融合 3 个既往项目：DigitalBrainOS (Agent schema + adapters) / metacog (知识链接) / gstack (编排恢复)

---

## TL;DR

**交付物**: 5 个任务，4 个可并行，预估 ~11h
**核心价值**: agentmesh Agent 定义深度提升 + KOS 认知框架内容化 + P0 浏览器编排能力恢复

```
Wave 1 (完全并行, 4任务, ~3h):
├── T1: AgentDefinition 类型扩展 (agentmesh types.ts)     [~2h]
├── T2: knowledge_links.yaml (KOS self ← metacog)         [~1h]
├── T3: gstack 恢复 + orchestrator 接口标准化             [~3h]
└── T4: DigitalBrainOS adapters 迁移 (Iris connector)     [逐步]

Wave 2 (依赖 T3, ~1h):
└── T5: gstack → Forge 注册                               [~1h]

Total: ~11h | 关键路径: T1 → (无) | 最大并行: 4
```

## 并发架构

```
T1 (agentmesh types.ts)        ─── (无下游)
T2 (KOS knowledge_links.yaml)  ─── (无下游)
T3 (gstack 恢复)                ─── T5 (Forge 注册)
T4 (Iris adapter)              ─── (无下游)
```

---

## TODOs

- [ ] 1. AgentDefinition 类型扩展

  **What to do**:
  - 读取 DigitalBrainOS/agents/ 目录中的 Agent schema 定义
  - 读取 agentmesh/packages/engine/src/types.ts 当前 `AgentDefinition` 接口
  - 在 `AgentDefinition` 中添加四个新字段:
    - `identity?: AgentIdentitySchema` — 深度身份 (personality/preferences/boundaries/communication_style)
    - `memory?: MemoryConfig` — 记忆配置 (short_term/long_term/working/episodic)
    - `collaboration?: CollaborationConfig` — 协作配置 (peer_agents/coordination_protocol)
    - `platform_adapters?: PlatformAdapter[]` — 外部平台适配器
  - 在 `types.ts` 中定义以上四个新增类型接口
  - 更新 `identity-manager.ts` 的 `declare()` 方法，从新增字段提取身份信息
  - `bun run build` 通过

  **Must NOT do**:
  - 不改现有字段的语义
  - 不改任何运行时行为（仅类型扩展，可选字段）
  - 不改测试文件

  **Agent Profile**: `quick` (TypeScript 类型定义)
  **Parallelization**: Wave 1, parallel with T2/T3/T4
  **Blocks**: 无
  **Blocked By**: 无

  **Acceptance Criteria**:
  - [ ] `types.ts` 包含 AgentIdentitySchema/MemoryConfig/CollaborationConfig/PlatformAdapter 四个接口
  - [ ] `AgentDefinition` 包含新增四个可选字段
  - [ ] `bun run build` 在 engine 层级通过
  - [ ] 现有测试全部通过

  **QA**:
  ```
  Scenario: 类型扩展编译通过
    Tool: Bash
    Steps:
      1. cd agentmesh/packages/engine
      2. bun run build
    Expected: exit 0, 无 tsc 错误
  ```

  **Commit**: `feat(types): extend AgentDefinition with identity/memory/collaboration/adapters`

- [ ] 2. KOS self — metacog 知识链接

  **What to do**:
  - 创建 KOS domain/self/knowledge_links.yaml
  - 定义 metacog → KOS cognitive_frameworks 的映射关系
  - 映射表（从 metacog 扫描结果整理）:
    - metacog 01-theories/thinking-frameworks → self.cognitive_frameworks.decision_making
    - metacog 01-theories/cognitive-biases → self.cognitive_frameworks.biases
    - metacog 01-theories/systems-thinking → self.cognitive_frameworks.reasoning
    - metacog 02-practices/ → self.cognitive_frameworks.applied
    - metacog 03-foundations/ → self.cognitive_frameworks.foundations
  - YAML 格式可解析，每项包含: name/source/mapped_to/tags

  **Must NOT do**:
  - 不复制 metacog 内容到 KOS（只建立链接）
  - 不改 KOS self/ 现有代码

  **Agent Profile**: `quick` (YAML 文档)
  **Parallelization**: Wave 1, parallel with T1/T3/T4
  **Blocks**: 无
  **Blocked By**: 无

  **Acceptance Criteria**:
  - [ ] domain/self/knowledge_links.yaml 存在
  - [ ] 包含 5+ 个链接条目
  - [ ] YAML 格式可解析

  **QA**:
  ```
  Scenario: knowledge_links.yaml 可解析
    Tool: Bash
    Steps:
      1. python3 -c "import yaml; d=yaml.safe_load(open('domain/self/knowledge_links.yaml')); print(len(d), 'links')"
    Expected: 输出 links 数，无 YAML 错误
  ```

  **Commit**: `feat(kos): add metacog knowledge links to self domain`

- [ ] 3. gstack 恢复 + orchestrator 接口标准化

  **What to do**:
  - 从 `_archived/gstack/` 复制到 `Workspace/gstack/`
  - 读取 `agents/orchestrators-index.md` 了解 20 个 orchestrator
  - 创建 `src/backends.ts` 定义统一 backend 接口（适配 Interceptor/Browser 作为执行引擎）
  - 创建 `src/orchestrator-runner.ts` — 解析 orchestrator 定义并路由到对应 backend
  - 确保不修改原有 orchestrator 定义（只加适配层）

  **Must NOT do**:
  - 不删除原有 orchestrator 代码
  - 不立即实现所有 20 个（只加运行时层）
  - 不引入新依赖

  **Agent Profile**: `quick` (TypeScript)
  **Parallelization**: Wave 1, parallel with T1/T2/T4
  **Blocks**: T5
  **Blocked By**: 无

  **Acceptance Criteria**:
  - [ ] `Workspace/gstack/` 存在，与 `_archived/gstack` 内容一致
  - [ ] `src/backends.ts` 定义 `BrowserBackend` 接口（execute/batch/screenshot）
  - [ ] `src/orchestrator-runner.ts` 可解析 orchestrator index

  **QA**:
  ```
  Scenario: gstack 恢复 + runner 接口定义
    Tool: Bash
    Steps:
      1. ls gstack/agents/orchestrators-index.md
      2. ls gstack/src/backends.ts
    Expected: 两个文件都存在
  ```

  **Commit**: `feat(gstack): restore and add orchestrator runner interface`

- [ ] 4. DigitalBrainOS adapters → Iris 连接器迁移

  **What to do**:
  - 读取 DigitalBrainOS/adapters/ 中所有适配器代码
  - 评估哪些适配器（Telegram/itchat/飞书）可复用到 Iris 连接器体系
  - 创建一个适配器迁移计划（adapter-migration-plan.md）
  - 至少迁移 1 个适配器（优先 Telegram）到 Iris connectors/
  - 遵循 Iris 现有 connector 模式（参考 obsidian connector）

  **Must NOT do**:
  - 不改 DigitalBrainOS 原有适配器代码（只复制修改）
  - 不引入外部 API 依赖

  **Agent Profile**: `quick` (Python)
  **Parallelization**: Wave 1, parallel with T1/T2/T3
  **Blocks**: 无
  **Blocked By**: 无

  **Acceptance Criteria**:
  - [ ] adapter-migration-plan.md 存在
  - [ ] 至少 1 个 adapter 迁移到 Iris/connectors/
  - [ ] Iris python 语法验证通过

  **Commit**: `feat(iris): migrate Telegram adapter from DigitalBrainOS`

- [ ] 5. gstack → Forge 注册

  **What to do**:
  - 将 gstack 的 20 个 orchestrator 注册到 Forge 工具库
  - 在 Forge 中创建 `category: browser-orchestration` 或在已有分类中注册
  - 注册方式：Forge 的 tool_registry 或 graph
  - 每个 orchestrator 注册为：`gstack:{orchestrator-name}`
  - 注册后可以通过 `forge search` 搜索到

  **Must NOT do**:
  - 不改 Forge 核心注册逻辑
  - 不改 gstack 代码

  **Agent Profile**: `quick` (Forge 注册)
  **Parallelization**: Wave 2, sequential after T3
  **Blocks**: 无
  **Blocked By**: T3

  **Acceptance Criteria**:
  - [ ] `forge search gstack:` 返回 20 个 orchestrator
  - [ ] 每个 orchestrator 有名称和描述

  **QA**:
  ```
  Scenario: Forge 能搜索到 gstack orchestrator
    Tool: Bash
    Steps:
      1. forge search gstack: 或 forge list --category browser-orchestration
    Expected: 返回 20 条结果
  ```

  **Commit**: `feat(forge): register gstack browser orchestrators`

---

## 检查点

### CP-1: 类型扩展
- [ ] `bun run build` pass on agentmesh/packages/engine

### CP-2: 知识链接
- [ ] `python3 -c "import yaml; yaml.safe_load(open('domain/self/knowledge_links.yaml'))"` pass

### CP-3: gstack 恢复
- [ ] gstack/ 目录存在，与 _archived 一致
- [ ] src/backends.ts + src/orchestrator-runner.ts 存在

### CP-4: Iris adapter
- [ ] adapter-migration-plan.md 存在
- [ ] 新 connector 文件存在

### CP-5: Forge 注册
- [ ] forge search gstack: 可搜索

---

## 最终验证
- [ ] agentmesh 编译通过，测试通过
- [ ] KOS knowledge_links.yaml 可解析
- [ ] gstack 恢复运行
- [ ] Iris 新 connector 注册
- [ ] Forge 可搜索 gstack orchestrator

## Commit Strategy
- T1: `feat(types): extend AgentDefinition with identity/memory/collaboration/adapters`
- T2: `feat(kos): add metacog knowledge links to self domain`
- T3: `feat(gstack): restore and add orchestrator runner interface`
- T4: `feat(iris): migrate Telegram adapter from DigitalBrainOS`
- T5: `feat(forge): register gstack browser orchestrators`
