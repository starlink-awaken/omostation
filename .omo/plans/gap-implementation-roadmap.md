# 个人AI操作系统 — 差距实施路线图

## TL;DR

> **核心目标**: 将差距分析发现的11个🔴关键差距、3个🟡警告差距系统性地落地为可执行任务，按MECH-05 Wave模型推进
>
> **交付物**:
> - A1 Agent身份声明系统（arcnode + agentmesh + SharedBrain）
> - pipeline:json协议在至少3个工具中落地
> - EG1-EG6 + A1-A10 验证脚本部署到arcnode
> - Resource Accounting 定价统一
> - EG5 相位锁定机制实现
>
> **预计工作量**: Large（4 Phase × 2-3 Sprint × 3-5 Wave）
> **并行执行**: YES — 4 Phase串行，Phase内Wave并行
> **关键路径**: Phase 1(T1→T3→T5) → Phase 2(T7→T10) → Phase 3(T13→T15) → Phase 4(T17→T19)

---

## Context

### 原始需求
用户要求基于差距分析制定详细实施方案和路线图，按照迭代机制和流程推进个人AI操作系统项目落地。

### 访谈摘要
**关键讨论:**
- 文档按SSOT本体论原则组织
- 宪法文件直接更新（非修正案方式）
- A1-A10 Agent约束为MUST级别（A8例外为SHOULD）—故意硬约束
- 按照MECH-05 Wave模型推进（Phase→Sprint→Wave→Task）
- pipeline:json为宪法第11种传输协议

### 研究发现
**差距热力图（42条约束审计）:**
- 🔴 11个关键差距（A1/A2/A4/A5/A6/A7/A9/A10、pipeline-input、pipeline:json、EG5）
- 🟡 3个警告差距（A3验证50%、A8资源40%、Pipeline编排25%、Resource定价70%）
- ✅ 良好差距：Agora降级100%、Boulder跟踪100%、约束执行引擎80%

**探索发现:**
- arcnode有14个验证脚本（S1-S8/T1-T7/R1-R6/G1-G5），需扩展EG+A
- agentmesh有Guardian/AnomalyRuleEngine/GovernanceCoordinator（1265+1016+1197 LOC）但无身份声明
- SharedBrain有`sovereignty_level`和`AgentRole`但未声明
- eidos是唯一完整编排器；kos/minerva/ontoderive有`--pipeline-output`但不消费`--pipeline-input`

### Metis审查
**识别差距（已解决）:**
- 缺少Phase间回归测试策略 → 添加Phase间验证门
- 资源定价模型未统一 → Phase 1统一
- Agent身份声明依赖运行时环境 → 需要环境检测机制

---

## Work Objectives

### 核心目标
将差距分析发现的11个🔴关键差距、3个🟡警告差距系统性地落地为可执行任务，按MECH-05 Wave模型推进

### 具体交付物
- A1 Agent身份声明系统（arcnode验证 + agentmesh运行时 + SharedBrain角色）
- pipeline:json协议在至少3个核心工具中落地
- EG1-EG6 + A2-A10 验证脚本部署到arcnode
- Resource Accounting 统一定价系统
- EG5 相位锁定机制
- 端到端集成测试

### 完成定义
- [ ] `arcnode validate --constraint A1` 通过
- [ ] `agentmesh identity verify` 返回有效身份
- [ ] `ontoderive --pipeline-input pipeline.json` 正确消费管线输入
- [ ] `arcnode validate --constraint EG1` 通过（全部EG+A）
- [ ] Resource定价在3个项目中一致（agentmesh/SharedBrain/MetaOS）
- [ ] Phase锁定在2个工具间正确执行

### Must Have
- A1 Agent身份声明系统（其余A约束的先决条件）
- pipeline:json协议至少3个工具实现
- EG1-EG6验证脚本
- A2-A10验证脚本
- Resource统一定价

### Must NOT Have（护栏）
- 不修改现有S/T/R/G约束的语义（仅扩展）
- 不破坏arcnode现有14个验证脚本
- 不引入新的传输协议（仅扩展pipeline:json）
- 不在Phase 1-3期间修改宪法核心§1-§8
- AI slop: 不添加过度抽象层、不创建未使用的接口、不写空注释

### Spec Framework Integration
- **Detected Framework**: 无SDD框架（openspec/、.specify/、_bmad/ 均未检测到）
- **Config File**: N/A
- **Active Specs**: N/A

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES — arcnode有14个验证脚本，bun test在agentmesh/SharedBrain存在
- **Automated tests**: Tests-after（每个任务完成后添加测试）
- **Framework**: bun test
- **If TDD**: 不采用，采用Tests-after策略

### QA Policy
每个任务必须包含agent-executed QA场景。证据保存到 `.omo/evidence/task-{N}-{scenario-slug}.{ext}`

- **arcnode验证**: Bash — 运行验证脚本，检查exit code
- **agentmesh/SharedBrain**: Bash — bun test，检查通过数
- **Pipeline协议**: Bash — 运行CLI命令，检查JSON输出
- **Resource定价**: Bash — 比较三个项目的定价配置

---

## Execution Strategy

### Parallel Execution Waves

```
Phase 1 — Foundation 硬基建 (Sprint 1-2, Wave 1-3):
├── T1: A1 Agent身份声明规范与arcnode验证 [deep]
├── T2: pipeline:json 协议规范文档 [quick]
├── T3: A1 Agent身份声明 — agentmesh运行时实现 [deep]
├── T4: A1 Agent身份声明 — SharedBrain角色桥接 [unspecified-high]
├── T5: pipeline:json — ontoderive 消费端实现 [deep]
├── T6: pipeline:json — eidos 消费端实现 [unspecified-high]
└── T7: Resource统一定价模型设计与实现 [unspecified-high]

Phase 2 — Enforcement 硬执行 (Sprint 3-4, Wave 4-6):
├── T8: EG1-EG3 验证脚本 [deep]
├── T9: EG4-EG6 验证脚本 [deep]
├── T10: A2-A5 验证脚本 [deep]
├── T11: A6-A8 验证脚本 [deep]
├── T12: A9-A10 验证脚本 [deep]
└── T13: CI集成 — arcnode验证加入pre-commit [quick]

Phase 3 — Observability 可观测 (Sprint 5, Wave 7-8):
├── T14: EG5 相位锁定机制 [deep]
├── T15: 约束合规仪表板 [visual-engineering]
└── T16: Pipeline编排可观测性 [unspecified-high]

Phase 4 — Hardening 硬化 (Sprint 6, Wave 9-10):
├── T17: 端到端集成测试 [deep]
├── T18: 宪法更新 — 注册新约束 [quick]
└── T19: 文档同步 — wiki/story更新 [writing]

Phase FINAL (After ALL tasks — 4 parallel reviews):
├── F1: 合规审计 (oracle)
├── F2: 代码质量审查 (unspecified-high)
├── F3: 手动QA验证 (unspecified-high)
└── F4: 范围保真检查 (deep)
```

### Dependency Matrix

| Task | Blocks | Blocked By |
|------|--------|------------|
| T1  | T3, T4, T8-T12 | None |
| T2  | T5, T6 | None |
| T3  | T13 | T1 |
| T4  | T13 | T1 |
| T5  | T14, T16 | T2 |
| T6  | T14, T16 | T2 |
| T7  | T15 | None |
| T8  | T13 | T1 |
| T9  | T13 | T1 |
| T10 | T13 | T1 |
| T11 | T13 | T1 |
| T12 | T13 | T1 |
| T13 | T17 | T8-T12 |
| T14 | T17 | T5 |
| T15 | T17 | T7 |
| T16 | T17 | T5, T6 |
| T17 | F1-F4 | T14, T15, T16 |
| T18 | T17 | T8-T12 |
| T19 | T17 | T18 |

**Critical Path**: T1 → T3 → T13 → T17 → F1-F4
**Parallel Speedup**: ~60% faster than sequential (Phase内任务可并行）

### Agent Dispatch Summary

- **Phase 1** (7 tasks): T1→deep, T2→quick, T3→deep, T4→unspecified-high, T5→deep, T6→unspecified-high, T7→unspecified-high
- **Phase 2** (6 tasks): T8→deep, T9→deep, T10→deep, T11→deep, T12→deep, T13→quick
- **Phase 3** (3 tasks): T14→deep, T15→visual-engineering, T16→unspecified-high
- **Phase 4** (3 tasks): T17→deep, T18→quick, T19→writing
- **FINAL** (4 tasks): F1→oracle, F2→unspecified-high, F3→unspecified-high, F4→deep

---

## TODOs

- [x] 1. A1 Agent身份声明规范与arcnode验证脚本

  **What to do**:
  - 在 `arcnode/scripts/` 创建 `validate-A1-identity.sh` 验证脚本
  - 定义 A1 约束的YAML规范：`agent_identity` 必须包含 `id`、`role`、`sovereignty_level`、`capabilities` 四个必填字段
  - 验证逻辑：检查Agent启动时是否声明了身份文件（`agent-identity.yaml`或等价JSON），字段完整性、格式合规
  - 更新 `arcnode/scripts/INDEX.md` 注册新脚本
  - 测试：创建合法和非法的身份文件，验证脚本能正确区分

  **Must NOT do**:
  - 不修改现有 S/T/R/G 约束脚本
  - 不引入新的传输协议
  - 不创建额外的抽象层

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: A1是架构级约束，需要深入理解多个项目的身份模型
  - **Skills**: [`systematic-debugging`]
    - `systematic-debugging`: 验证脚本需要严格调试边界条件

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T2, T7)
  - **Blocks**: T3, T4, T8-T12
  - **Blocked By**: None (可立即开始)

  **References**:
  **Pattern References**:
  - `arcnode/scripts/validate-S1-safety.sh` — 现有验证脚本模式（入口检查、YAML解析、exit code）
  - `arcnode/scripts/validate-T1-tool-registration.sh` — 工具注册验证模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` — A1约束定义
  - `~/Documents/学习进化/基建架构/AGENT.md` — P10-P7角色模型

  **Test References**:
  - `arcnode/tests/validate-S1.test.sh` — 现有验证测试模式

  **External References**:
  - 无（内部项目规范）

  **WHY Each Reference Matters**:
  - `validate-S1-safety.sh`：这是最成熟的验证脚本，是所有新脚本的模板
  - `constraints.md`：A1约束的权威定义源
  - `AGENT.md`：角色模型定义，A1身份必须与之对齐

  **Acceptance Criteria**:
  - [ ] `arcnode/scripts/validate-A1-identity.sh` 文件存在且可执行
  - [ ] `arcnode validate --constraint A1` 返回 exit code 0（对合法身份文件）
  - [ ] `arcnode validate --constraint A1` 返回 exit code 1（对缺失/非法身份文件）
  - [ ] INDEX.md 已更新注册新脚本

  **QA Scenarios**:

  ```
  Scenario: A1 合法身份文件验证通过
    Tool: Bash (arcnode)
    Preconditions: 存在合法 agent-identity.yaml 包含 id/role/sovereignty_level/capabilities
    Steps:
      1. 创建 /tmp/test-agent-identity.yaml，包含完整的四字段
      2. 运行 arcnode validate --constraint A1 --identity-file /tmp/test-agent-identity.yaml
      3. 检查 exit code 为 0
    Expected Result: exit code 0, 输出包含 "A1 PASS"
    Failure Indicators: exit code 非0, 输出包含 "A1 FAIL"
    Evidence: .omo/evidence/task-1-a1-valid-pass.txt

  Scenario: A1 非法身份文件验证失败
    Tool: Bash (arcnode)
    Preconditions: 缺失字段或格式错误
    Steps:
      1. 创建 /tmp/test-bad-identity.yaml，仅包含 id 字段（缺少 role/sovereignty_level/capabilities）
      2. 运行 arcnode validate --constraint A1 --identity-file /tmp/test-bad-identity.yaml
      3. 检查 exit code 为 1
    Expected Result: exit code 1, 输出包含 "A1 FAIL" 和具体缺失字段
    Failure Indicators: exit code 0（应该失败但通过了）
    Evidence: .omo/evidence/task-1-a1-invalid-fail.txt
  ```

  **Commit**: YES (groups with T2)
  - Message: `feat(arcnode): add A1 agent identity validation constraint`
  - Files: `arcnode/scripts/validate-A1-identity.sh`, `arcnode/scripts/INDEX.md`
  - Pre-commit: `arcnode validate --constraint A1`

- [x] 2. pipeline:json 协议规范文档

  **What to do**:
  - 在 `~/Documents/学习进化/基建架构/宪法/interface_contract.md` 中扩展 §5，定义 `pipeline:json` 协议的完整规范
  - 规范包含：输入schema（`pipeline_input`字段）、输出schema（`pipeline_output`字段）、错误格式、版本号
  - 参考现有MECH-03（管线编排）中的Pipeline Protocol v1.0定义
  - 确保 `pipeline:json` 与现有10种协议（S/T/R/G/pipeline-input/pipeline-output/health/ready/capability/metadata）的命名一致

  **Must NOT do**:
  - 不创建新协议文件，只在现有 `interface_contract.md` 中扩展
  - 不修改现有协议定义
  - 不引入与MECH-03冲突的概念

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯文档任务，规范的增量扩展，无需深度推理
  - **Skills**: []
    - 无需额外技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T7)
  - **Blocks**: T5, T6
  - **Blocked By**: None (可立即开始)

  **References**:
  **Pattern References**:
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — 现有10种协议的格式和命名规范
  - `~/Documents/学习进化/基建架构/机制/MECH-03-管线编排.md` — Pipeline Protocol v1.0定义

  **Test References**:
  - 无（纯文档任务）

  **External References**:
  - 无

  **WHY Each Reference Matters**:
  - `interface_contract.md`：现有协议的权威定义，新规范必须与之风格一致
  - `MECH-03`：pipeline的实际机制定义，规范必须反映其实际工作方式

  **Acceptance Criteria**:
  - [ ] `interface_contract.md` §5 包含 `pipeline:json` 协议定义
  - [ ] 定义包含：input schema、output schema、error format、version
  - [ ] 命名与现有10种协议一致（kebab-case）

  **QA Scenarios**:

  ```
  Scenario: pipeline:json 协议规范完整性检查
    Tool: Bash (grep)
    Preconditions: interface_contract.md 已更新
    Steps:
      1. grep -c "pipeline:json" ~/Documents/学习进化/基建架构/宪法/interface_contract.md
      2. grep "schema:" ~/Documents/学习进化/基建架构/宪法/interface_contract.md | grep pipeline
      3. grep "version:" ~/Documents/学习进化/基建架构/宪法/interface_contract.md | grep pipeline
    Expected Result: 至少3处pipeline:json引用，包含schema和version定义
    Failure Indicators: 引用少于3处或缺少schema/version
    Evidence: .omo/evidence/task-2-pipeline-json-spec.txt

  Scenario: pipeline:json 与MECH-03一致性
    Tool: Bash (diff)
    Preconditions: MECH-03文件和interface_contract.md均存在
    Steps:
      1. 提取MECH-03中的Pipeline Protocol定义关键字段
      2. 对比interface_contract.md中的pipeline:json定义
      3. 检查字段名、必填项、版本号是否一致
    Expected Result: 字段名和必填项100%一致
    Failure Indicators: 任何不一致（如字段名不同、缺少必填项）
    Evidence: .omo/evidence/task-2-mech03-consistency.txt
  ```

  **Commit**: YES (groups with T1)
  - Message: `docs(constitution): add pipeline:json protocol specification`
  - Files: `~/Documents/学习进化/基建架构/宪法/interface_contract.md`
  - Pre-commit: `grep -c "pipeline:json" ~/Documents/学习进化/基建架构/宪法/interface_contract.md`

- [x] 3. A1 Agent身份声明 — agentmesh运行时实现

  **What to do**:
  - 在 `agentmesh/packages/engine/src/` 创建 `identity/` 模块
  - 实现 `AgentIdentity` 接口和 `IdentityManager` 类
  - `AgentIdentity` 接口：`id: string`, `role: AgentRole`, `sovereignty_level: SovereigntyLevel`, `capabilities: string[]`, `declared_at: ISO8601timestamp`
  - `IdentityManager` 类：`declare(identity: AgentIdentity)`, `verify(agentId: string): VerificationResult`, `revoke(agentId: string): void`
  - 与现有 `Guardian`/`AnomalyRuleEngine`/`GovernanceCoordinator` 集成（1265+1016+1197 LOC）
  - 添加单元测试覆盖：合法声明、重复声明、缺失字段、格式非法

  **Must NOT do**:
  - 不修改 Guardian/AnomalyRuleEngine/GovernanceCoordinator 的核心逻辑
  - 不引入新的依赖包
  - 不创建未在A1规范中定义的字段

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要深入理解agentmesh的Agent生命周期和治理架构
  - **Skills**: [`systematic-debugging`]
    - `systematic-debugging`: 集成3个现有子系统需要严格的边界条件测试

  **Parallelization**:
  - **Can Run In Parallel**: YES（与T1脚本无关，但逻辑依赖T1规范）
  - **Parallel Group**: Wave 2 (after T1)
  - **Blocks**: T13
  - **Blocked By**: T1（需要A1规范定义）

  **References**:
  **Pattern References**:
  - `agentmesh/packages/engine/src/governance/guardian.ts` — Guardian类模式（1265 LOC）
  - `agentmesh/packages/engine/src/governance/anomaly-rule-engine.ts` — 异常检测模式（1016 LOC）

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` — A1约束定义
  - `~/Documents/学习进化/基建架构/AGENT.md` — P10-P7角色模型

  **Test References**:
  - `agentmesh/packages/engine/src/__tests__/guardian.test.ts` — Guardian测试模式

  **Why Each Reference Matters**:
  - `guardian.ts`：身份管理必须与Guardian的治理钩子集成
  - `anomaly-rule-engine.ts`：身份验证失败应触发异常规则

  **Acceptance Criteria**:
  - [ ] `agentmesh/packages/engine/src/identity/agent-identity.ts` 文件存在
  - [ ] `agentmesh/packages/engine/src/identity/identity-manager.ts` 文件存在
  - [ ] `bun test packages/engine/src/identity/` 全部通过
  - [ ] `AgentIdentity` 接口包含 id/role/sovereignty_level/capabilities/declared_at
  - [ ] `IdentityManager.declare()` 正确注册身份
  - [ ] `IdentityManager.verify()` 正确验证合法/非法身份

  **QA Scenarios**:

  ```
  Scenario: Agent身份声明与验证
    Tool: Bash (bun test)
    Preconditions: agentmesh项目可构建
    Steps:
      1. 创建合法AgentIdentity实例
      2. 调用 IdentityManager.declare(identity)
      3. 调用 IdentityManager.verify(identity.id)
      4. 检查返回 VerificationResult.success === true
    Expected Result: verify 返回 success=true
    Failure Indicators: verify 返回 success=false 或抛出异常
    Evidence: .omo/evidence/task-3-identity-declare-verify.txt

  Scenario: 非法身份拒绝
    Tool: Bash (bun test)
    Preconditions: agentmesh项目可构建
    Steps:
      1. 创建缺少role字段的AgentIdentity
      2. 调用 IdentityManager.declare(identity)
      3. 检查是否抛出 ValidationError
    Expected Result: declare 抛出 ValidationError，包含 "missing required field: role"
    Failure Indicators: declare 不抛异常（应该拒绝但接受了）
    Evidence: .omo/evidence/task-3-identity-invalid-reject.txt
  ```

  **Commit**: YES
  - Message: `feat(agentmesh): implement A1 agent identity declaration runtime`
  - Files: `agentmesh/packages/engine/src/identity/`, `agentmesh/packages/engine/src/__tests__/identity/`
  - Pre-commit: `bun test packages/engine/src/identity/`

- [x] 4. A1 Agent身份声明 — SharedBrain角色桥接

  **What to do**:
  - 在 `SharedBrain/organs/` 找到 `AgentRole` 和 `sovereignty_level` 的定义位置
  - 创建桥接模块 `identity_bridge.py`，将 A1 `AgentIdentity` 映射到 SharedBrain 的 `AgentRole`
  - 映射逻辑：A1.id → SharedBrain.agent_id, A1.role → SharedBrain.AgentRole, A1.sovereignty_level → SharedBrain.sovereignty_level
  - 添加单元测试

  **Must NOT do**:
  - 不修改 SharedBrain 现有 `AgentRole` 定义
  - 不引入新的Python依赖
  - 不创建双向同步（仅 A1→SharedBrain 单向）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解两个不同项目（TypeScript/Python）的身份模型并建立桥接
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES（与T3并行，T3在agentmesh，T4在SharedBrain）
  - **Parallel Group**: Wave 2 (after T1)
  - **Blocks**: T13
  - **Blocked By**: T1（需要A1规范定义）

  **References**:
  **Pattern References**:
  - `SharedBrain/organs/` — 现有器官系统模式（Python类、定义文件）
  - `SharedBrain/` 根目录 — 项目结构和测试模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` — A1约束定义
  - `~/Documents/学习进化/基建架构/AGENT.md` — P10-P7角色模型

  **Test References**:
  - `SharedBrain/tests/` — 现有测试模式（pytest）

  **Why Each Reference Matters**:
  - `SharedBrain/organs/`：桥接模块必须匹配现有器官系统的导入/初始化模式
  - `constraints.md`：A1身份字段定义的权威来源

  **Acceptance Criteria**:
  - [ ] `SharedBrain/nucleus/identity_bridge.py` 文件存在
  - [ ] 桥接函数 `map_identity_to_role(agent_identity: dict) -> AgentRole` 存在
  - [ ] `pytest SharedBrain/tests/test_identity_bridge.py` 通过
  - [ ] 映射覆盖：id→agent_id, role→AgentRole, sovereignty_level→sovereignty_level

  **QA Scenarios**:

  ```
  Scenario: 合法身份映射到AgentRole
    Tool: Bash (pytest)
    Preconditions: SharedBrain项目可测试
    Steps:
      1. 构造A1 AgentIdentity dict（id="test-agent", role="executor", sovereignty_level="supervised", capabilities=["read","write"]）
      2. 调用 map_identity_to_role(identity_dict)
      3. 检查返回的AgentRole对象字段完整
    Expected Result: 返回AgentRole对象，agent_id="test-agent", role=EXECUTOR, sovereignty_level=SUPERVISED
    Failure Indicators: 映射失败或字段缺失
    Evidence: .omo/evidence/task-4-bridge-valid-map.txt

  Scenario: 缺失字段处理
    Tool: Bash (pytest)
    Preconditions: SharedBrain项目可测试
    Steps:
      1. 构造缺少sovereignty_level的AgentIdentity dict
      2. 调用 map_identity_to_role(identity_dict)
      3. 检查是否抛出映射错误并回退到默认值
    Expected Result: 抛出 IdentityMappingError 或回退到 sovereignty_level=autonomous（SharedBrain默认值）
    Failure Indicators: 无声失败或返回None
    Evidence: .omo/evidence/task-4-bridge-missing-field.txt
  ```

  **Commit**: YES
  - Message: `feat(sharedbrain): bridge A1 identity to AgentRole model`
  - Files: `SharedBrain/nucleus/identity_bridge.py`, `SharedBrain/tests/test_identity_bridge.py`
  - Pre-commit: `pytest SharedBrain/tests/test_identity_bridge.py`

- [x] 5. pipeline:json — ontoderive 消费端实现

  **What to do**:
  - 在 `ontoderive/` 项目中实现 `--pipeline-input` CLI参数消费
  - 解析 `pipeline:json` 格式输入（参考T2中定义的schema）
  - 验证输入schema版本兼容性
  - 将管线输入映射到ontoderive内部的推理参数
  - 添加单元测试和集成测试

  **Must NOT do**:
  - 不修改ontoderive现有的 `--pipeline-output` 输出逻辑
  - 不引入新的依赖（使用现有CLI框架）
  - 不破坏现有CLI参数接口

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要理解ontoderive的21+子命令和内部推理管道
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES（与T6并行，不同项目）
  - **Parallel Group**: Wave 2 (after T2)
  - **Blocks**: T14, T16
  - **Blocked By**: T2（需要pipeline:json规范定义）

  **References**:
  **Pattern References**:
  - `ontoderive/` 项目中的CLI入口文件 — 现有子命令模式
  - `ontoderive/` 项目中的 `--pipeline-output` 实现 — 输出端模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — pipeline:json schema
  - `~/Documents/学习进化/基建架构/机制/MECH-03-管线编排.md` — Pipeline Protocol v1.0

  **Test References**:
  - `ontoderive/tests/` — 现有测试模式

  **Why Each Reference Matters**:
  - CLI入口文件：新参数必须遵循现有子命令注册模式
  - `--pipeline-output`：消费端是输出端的镜像，必须对齐数据格式

  **Acceptance Criteria**:
  - [ ] `ontoderive --pipeline-input test-pipeline.json` 正确消费输入
  - [ ] 无效pipeline JSON输入返回明确错误信息
  - [ ] 版本不兼容时返回版本错误
  - [ ] `pytest` 测试通过

  **QA Scenarios**:

  ```
  Scenario: 合法pipeline输入消费
    Tool: Bash (ontoderive CLI)
    Preconditions: ontoderive可运行，test-pipeline.json符合schema
    Steps:
      1. 创建 test-pipeline.json 包含有效L0数据
      2. 运行 ontoderive --pipeline-input test-pipeline.json --dry-run
      3. 检查输出包含正确解析的参数
    Expected Result: 成功消费输入，参数正确映射到推理参数
    Failure Indicators: 解析失败或参数映射错误
    Evidence: .omo/evidence/task-5-ontoderive-pipeline-input.txt

  Scenario: 无效pipeline输入错误处理
    Tool: Bash (ontoderive CLI)
    Preconditions: ontoderive可运行
    Steps:
      1. 创建 invalid-pipeline.json 包含错误字段
      2. 运行 ontoderive --pipeline-input invalid-pipeline.json
      3. 检查返回明确的验证错误
    Expected Result: exit code 1，输出包含 "pipeline input validation error" 和具体字段
    Failure Indicators: exit code 0（应该失败但通过了）
    Evidence: .omo/evidence/task-5-ontoderive-invalid-input.txt
  ```

  **Commit**: YES
  - Message: `feat(ontoderive): implement --pipeline-input consumer`
  - Files: `ontoderive/src/cli.rs`（或等价CLI入口）, `ontoderive/src/pipeline_input.rs`, `ontoderive/tests/test_pipeline_input.rs`
  - Pre-commit: `ontoderive --pipeline-input test-pipeline.json --dry-run`

- [x] 6. pipeline:json — eidos 消费端实现（编排器侧）

  **What to do**:
  - 在 `eidos/` 项目中实现 `--pipeline-input` CLI参数消费
  - eidos作为唯一完整编排器（L3级），需要消费上游管线输出并编排下游工具
  - 实现：解析输入、验证schema、分配到内部编排引擎、传递到下游工具
  - 与ontoderive的 `--pipeline-output` 对接测试
  - 添加单元测试和端到端测试

  **Must NOT do**:
  - 不修改eidos现有的Schema验证逻辑
  - 不引入新依赖
  - 不破坏现有CLI接口

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解eidos的编排引擎和Schema验证体系
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES（与T5并行，不同项目）
  - **Parallel Group**: Wave 2 (after T2)
  - **Blocks**: T14, T16
  - **Blocked By**: T2（需要pipeline:json规范定义）

  **References**:
  **Pattern References**:
  - `eidos/` 项目中的编排器入口 — 现有编排模式
  - `eidos/` 项目中的Schema验证 — Eidos Schema验证模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — pipeline:json schema
  - `~/Documents/学习进化/基建架构/机制/MECH-03-管线编排.md` — L3编排器定义

  **Test References**:
  - `eidos/tests/` — 现有测试模式

  **Why Each Reference Matters**:
  - 编排器入口：新参数必须与现有编排引擎正确集成
  - MECH-03：eidos是L3级编排器，必须实现完整编排能力

  **Acceptance Criteria**:
  - [ ] `eidos orchestrate --pipeline-input test-pipeline.json` 正确消费输入
  - [ ] eidos能将输入分发到编排引擎并调度下游工具
  - [ ] 版本不兼容时返回明确错误
  - [ ] `pytest` 测试通过

  **QA Scenarios**:

  ```
  Scenario: eidos编排器消费pipeline输入
    Tool: Bash (eidos CLI)
    Preconditions: eidos可运行，test-pipeline.json符合schema
    Steps:
      1. 创建 test-pipeline.json 包含L3编排数据
      2. 运行 eidos orchestrate --pipeline-input test-pipeline.json --dry-run
      3. 检查编排引擎正确解析和分发
    Expected Result: 成功消费，编排计划正确生成
    Failure Indicators: 解析失败或编排计划生成错误
    Evidence: .omo/evidence/task-6-eidos-pipeline-input.txt

  Scenario: eidos-ontoderive 端到端管线测试
    Tool: Bash (pipeline)
    Preconditions: ontoderive和eidos均可运行
    Steps:
      1. 运行 ontoderive derive --pipeline-output /tmp/pipeline-out.json
      2. 运行 eidos orchestrate --pipeline-input /tmp/pipeline-out.json --dry-run
      3. 检查数据从ontoderive正确传递到eidos
    Expected Result: eidos成功消费ontoderive的输出
    Failure Indicators: 数据丢失或格式不兼容
    Evidence: .omo/evidence/task-6-e2e-pipeline.txt
  ```

  **Commit**: YES
  - Message: `feat(eidos): implement --pipeline-input consumer for编排器`
  - Files: `eidos/src/orchestrator.rs`（或等价入口）, `eidos/src/pipeline_input.rs`, `eidos/tests/test_pipeline_input.rs`
  - Pre-commit: `eidos orchestrate --pipeline-input test-pipeline.json --dry-run`

- [x] 7. Resource统一定价模型设计与实现

  **What to do**:
  - 调研 agentmesh、SharedBrain、MetaOS 三个项目的资源定价模型当前状态
  - 设计统一定价模型：统一 `ResourcePrice` 类型定义（cost_per_token, cost_per_request, cost_per_second, currency）
  - 在三个项目中分别实现 `pricing_config.yaml`（或等价配置）
  - 在 `arcnode/scripts/` 创建 `validate-R-pricing.sh` 验证脚本
  - 添加跨项目价格一致性测试

  **Must NOT do**:
  - 不修改三个项目的核心定价逻辑（仅统一配置格式）
  - 不强制所有项目使用相同绝对价格（仅统一结构和单位）
  - 不引入新的计费系统

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要跨3个不同项目（TS/Python/Python）对齐定价模型
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES（与T1-T6无依赖）
  - **Parallel Group**: Wave 1 (with T1, T2)
  - **Blocks**: T15
  - **Blocked By**: None (可立即开始)

  **References**:
  **Pattern References**:
  - `agentmesh/packages/engine/src/governance/` — 现有治理和资源模型
  - `SharedBrain/nucleus/` — 现有定价配置
  - `MetaOS/engine/` — 现有资源模型

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` — R1-R6资源约束
  - `~/Documents/学习进化/基建架构/AGENT.md` — P10-P7角色模型

  **Test References**:
  - 三个项目各自的测试文件

  **Why Each Reference Matters**:
  - 三个项目的定价模型是出发点，必须理解现状才能统一
  - R1-R6定义了资源约束的规范边界

  **Acceptance Criteria**:
  - [ ] 三个项目都有 `pricing_config.yaml`（或等价），格式统一
  - [ ] `arcnode validate --constraint R7` 通过（R7为定价一致性约束，待创建）
  - [ ] 跨项目价格一致性测试通过

  **QA Scenarios**:

  ```
  Scenario: 统一定价配置格式验证
    Tool: Bash (jq)
    Preconditions: 三个项目均有pricing配置
    Steps:
      1. 对比三个项目的pricing_config.yaml schema
      2. 检查字段一致：cost_per_token, cost_per_request, cost_per_second, currency
      3. 验证所有必要字段存在
    Expected Result: 三个项目的schema完全一致
    Failure Indicators: 字段名不同或缺少必要字段
    Evidence: .omo/evidence/task-7-pricing-format.txt

  Scenario: arcnode验证定价一致性
    Tool: Bash (arcnode)
    Preconditions: arcnode验证脚本已更新
    Steps:
      1. 运行 arcnode validate --constraint R7
      2. 检查跨项目定价一致性
    Expected Result: exit code 0，输出 "R7 PASS"
    Failure Indicators: exit code 1，输出 "R7 FAIL" 和不一致详情
    Evidence: .omo/evidence/task-7-pricing-consistency.txt
  ```

  **Commit**: YES (groups with T1)
  - Message: `feat(resource): unify pricing model across agentmesh/SharedBrain/MetaOS`
  - Files: `agentmesh/config/pricing_config.yaml`, `SharedBrain/config/pricing_config.yaml`, `MetaOS/config/pricing_config.yaml`, `arcnode/scripts/validate-R-pricing.sh`
  - Pre-commit: `arcnode validate --constraint R7`

- [x] 8. EG1-EG3 工程治理验证脚本

  **What to do**:
  - 在 `arcnode/scripts/` 创建 `validate-EG1-engineering-init.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-EG2-architecture-design.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-EG3-structural-scaffold.sh` 验证脚本
  - EG1 验证逻辑：检查新项目是否包含 `CLAUDE.md`、`AGENTS.md`、`README.md`、`package.json`（或等价）
  - EG2 验证逻辑：检查 AGENTS.md 是否定义边界（定位/上下游/状态/依赖）、README.md 是否包含架构图或系统入口
  - EG3 验证逻辑：检查目录结构是否遵循 shell-tool-essence-ext 拓扑（每个函数/类单文件、按「能力+对象」命名）
  - 验证逻辑引用宪法中 EG1-EG3 的定义（`constraints.md` §EG1-EG3）
  - 更新 `arcnode/scripts/INDEX.md` 注册新脚本
  - 测试：创建合法和非合法的项目结构，验证脚本能正确区分

  **Must NOT do**:
  - 不修改现有 S1-S8/T1-T7/R1-R6/G1-G5 约束脚本
  - 不要求所有项目达到相同成熟度（仅检测"存在"而非"完善"）
  - 不创建额外的验证抽象层

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: EG1-EG3 是工程治理的基础层级，需要深度理解宪法定义并与 arcnode 框架集成
  - **Skills**: []
    - 脚本模式已高度成熟，无需额外技能

  **Parallelization**:
  - **Can Run In Parallel**: YES（T8-T12 互不依赖，均为独立验证脚本）
  - **Parallel Group**: Wave 3 (with T9, T10, T11, T12)
  - **Blocks**: T13
  - **Blocked By**: T1（需要 arcnode 验证脚本框架就绪）

  **References**:
  **Pattern References**:
  - `arcnode/scripts/validate-S1-safety.sh` — 现有验证脚本模板（入口检查、YAML 解析、exit code）
  - `arcnode/scripts/validate-T1-tool-registration.sh` — 工具注册验证模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` §EG1-EG3 — 约束定义

  **Test References**:
  - `arcnode/tests/validate-S1.test.sh` — 现有验证测试模式

  **Why Each Reference Matters**:
  - `validate-S1-safety.sh`：标准验证脚本模板，所有新脚本必须遵循其文件头/解析/退出码模式
  - `constraints.md` §EG1-EG3：约束的权威定义源，验证逻辑必须与定义一一对应

  **Acceptance Criteria**:
  - [ ] `validate-EG1-engineering-init.sh` 文件存在且可执行
  - [ ] `validate-EG2-architecture-design.sh` 文件存在且可执行
  - [ ] `validate-EG3-structural-scaffold.sh` 文件存在且可执行
  - [ ] `arcnode validate --constraint EG1` 返回 exit code 0（合法项目结构）
  - [ ] `arcnode validate --constraint EG1` 返回 exit code 1（缺失 CLAUDE.md 等文件）
  - [ ] INDEX.md 已更新注册三个新脚本

  **QA Scenarios**:

  ```
  Scenario: EG1 合法项目初始化检查通过
    Tool: Bash (arcnode)
    Preconditions: 存在符合 EG1 的合法项目目录
    Steps:
      1. 创建 /tmp/eg1-valid/ 包含 CLAUDE.md、AGENTS.md、README.md
      2. 运行 arcnode validate --constraint EG1 --project-dir /tmp/eg1-valid/
      3. 检查 exit code 为 0
    Expected Result: exit code 0, 输出包含 "EG1 PASS"
    Failure Indicators: exit code 非 0
    Evidence: .omo/evidence/task-8-eg1-pass.txt

  Scenario: EG1 缺失文件检查失败
    Tool: Bash (arcnode)
    Preconditions: 项目目录缺失 AGENTS.md
    Steps:
      1. 创建 /tmp/eg1-invalid/ 仅包含 CLAUDE.md（缺少 AGENTS.md 和 README.md）
      2. 运行 arcnode validate --constraint EG1 --project-dir /tmp/eg1-invalid/
      3. 检查 exit code 为 1
    Expected Result: exit code 1, 输出包含 "EG1 FAIL" 和具体缺失文件列表
    Failure Indicators: exit code 0（应该失败但通过了）
    Evidence: .omo/evidence/task-8-eg1-fail.txt

  Scenario: EG2 架构设计检查——合法 AGENTS.md 边界定义
    Tool: Bash (arcnode)
    Preconditions: 存在包含完整边界定义的 AGENTS.md
    Steps:
      1. 创建 /tmp/eg2-valid/AGENTS.md 包含定位/边界/上下游/状态/依赖字段
      2. 运行 arcnode validate --constraint EG2 --project-dir /tmp/eg2-valid/
      3. 检查 exit code 为 0
    Expected Result: exit code 0, 输出包含 "EG2 PASS"
    Failure Indicators: exit code 非 0 或边界字段检查遗漏
    Evidence: .omo/evidence/task-8-eg2-pass.txt

  Scenario: EG3 结构脚手架——函数/类单文件原则
    Tool: Bash (arcnode)
    Preconditions: 存在符合 EG3 的项目结构
    Steps:
      1. 创建 /tmp/eg3-valid/src/ 包含按「能力+对象」命名的单文件
      2. 运行 arcnode validate --constraint EG3 --project-dir /tmp/eg3-valid/
      3. 检查 exit code 为 0
    Expected Result: exit code 0, 输出包含 "EG3 PASS"
    Failure Indicators: exit code 非 0 或拓扑检查误判
    Evidence: .omo/evidence/task-8-eg3-pass.txt
  ```

  **Commit**: YES (groups with T9-T12)
  - Message: `feat(arcnode): add EG1-EG3 engineering governance validation scripts`
  - Files: `arcnode/scripts/validate-EG1-engineering-init.sh`, `arcnode/scripts/validate-EG2-architecture-design.sh`, `arcnode/scripts/validate-EG3-structural-scaffold.sh`, `arcnode/scripts/INDEX.md`
  - Pre-commit: `arcnode validate --constraint EG1 && arcnode validate --constraint EG2 && arcnode validate --constraint EG3`

- [x] 9. EG4-EG6 工程治理验证脚本

  **What to do**:
  - 在 `arcnode/scripts/` 创建 `validate-EG4-runtime-orchestration.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-EG5-phase-lock.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-EG6-external-interface.sh` 验证脚本
  - EG4 验证逻辑：检查项目是否暴露清晰的外部接口（CLI / MCP / API 至少一种），检查 `package.json` / `pyproject.toml` 中是否定义入口
  - EG5 验证逻辑：暂时仅验证"相位锁定声明"的存在性（在 AGENTS.md 中声明已定义相位锁或声明不适用），完整的运行时相位锁定在 Phase 3 T14 实现
  - EG6 验证逻辑：检查项目之间是否存在超出契约的交叉引用（不应直接 pip import 另一个项目，应走 CLI/MCP），标记警告而非禁止
  - 引用宪法中 EG4-EG6 的定义（`constraints.md` §EG4-EG6）
  - 更新 `arcnode/scripts/INDEX.md` 注册新脚本

  **Must NOT do**:
  - EG5 验证不做运行时锁检查（Phase 3 才实现运行时的相位锁定机制）
  - 不修改现有 S/T/R/G 约束脚本
  - EG6 验证仅警告不阻止（避免破坏现有工作流）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: EG4-EG6 涉及接口暴露、相位锁定、跨项目耦合检测，需要深度理解项目拓扑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T8, T10, T11, T12)
  - **Blocks**: T13
  - **Blocked By**: T1（需要 arcnode 验证脚本框架就绪）

  **References**:
  **Pattern References**:
  - `arcnode/scripts/validate-S1-safety.sh` — 标准验证脚本模板
  - `arcnode/scripts/validate-T4-semver.sh` — 接口版本验证模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` §EG4-EG6 — 约束定义
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — 接口暴露要求

  **Test References**:
  - `arcnode/tests/validate-S1.test.sh` — 测试模式

  **Why Each Reference Matters**:
  - `validate-T4-semver.sh`：接口版本验证的现有实现，EG4 的接口曝光验证可以复用其逻辑
  - `constraints.md` §EG4-EG6：约束的权威定义源，每个验证脚本的逻辑必须与之对齐

  **Acceptance Criteria**:
  - [ ] `validate-EG4-runtime-orchestration.sh` 文件存在且可执行
  - [ ] `validate-EG5-phase-lock.sh` 文件存在且可执行
  - [ ] `validate-EG6-external-interface.sh` 文件存在且可执行
  - [ ] `arcnode validate --constraint EG4` 返回 exit code 0（有 CLI/MCP/API 入口的项目）
  - [ ] `arcnode validate --constraint EG5` 返回 exit code 0（声明了相位锁）
  - [ ] `arcnode validate --constraint EG6` 返回 exit code 0 或警告（跨项目引用检查）
  - [ ] INDEX.md 已更新注册三个新脚本

  **QA Scenarios**:

  ```
  Scenario: EG4 外部接口检查
    Tool: Bash (arcnode)
    Preconditions: agentmesh 项目有 package.json + CLI 入口
    Steps:
      1. 运行 arcnode validate --constraint EG4 --project-dir /path/to/agentmesh
      2. 检查是否检测到 CLI 入口
    Expected Result: exit code 0, 输出 "EG4 PASS — detected CLI entry: ..."
    Failure Indicators: exit code 1 或误报无入口
    Evidence: .omo/evidence/task-9-eg4-pass.txt

  Scenario: EG5 相位锁定声明检查
    Tool: Bash (arcnode)
    Preconditions: SharedBrain 项目 AGENTS.md 定义了相位锁
    Steps:
      1. 运行 arcnode validate --constraint EG5 --project-dir /path/to/SharedBrain
      2. 检查是否找到相位锁定声明
    Expected Result: exit code 0, 输出 "EG5 PASS"
    Failure Indicators: exit code 1 或对无需相位锁的项目误报
    Evidence: .omo/evidence/task-9-eg5-pass.txt

  Scenario: EG6 跨项目引用警告
    Tool: Bash (arcnode)
    Preconditions: 跨项目间存在 import 引用
    Steps:
      1. 运行 arcnode validate --constraint EG6
      2. 检查是否标记跨项目引用
    Expected Result: exit code 0（仅警告不阻止）, 输出列出跨项目引用
    Failure Indicators: exit code 1（不应失败，仅警告）
    Evidence: .omo/evidence/task-9-eg6-warning.txt
  ```

  **Commit**: YES (groups with T8, T10-T12)
  - Message: `feat(arcnode): add EG4-EG6 engineering governance validation scripts`
  - Files: `arcnode/scripts/validate-EG4-runtime-orchestration.sh`, `arcnode/scripts/validate-EG5-phase-lock.sh`, `arcnode/scripts/validate-EG6-external-interface.sh`, `arcnode/scripts/INDEX.md`
  - Pre-commit: `arcnode validate --constraint EG4 && arcnode validate --constraint EG5 && arcnode validate --constraint EG6`

- [x] 10. A2-A5 Agent 约束验证脚本

  **What to do**:
  - 在 `arcnode/scripts/` 创建 `validate-A2-agent-safety.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-A3-agent-execution-trace.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-A4-agent-capability.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-A5-agent-auth-chain.sh` 验证脚本
  - A2 验证逻辑：检查 Agent 能否安全终止/中断/恢复（验证 `SIGTERM` 处理、超时机制、状态持久化）
  - A3 验证逻辑：（50% 初步）检查 Agent 运行日志中是否存在 session_id 和时间戳字段（`validate-A3-agent-execution-trace.sh` 目前 50% 实现，提升到 100%）
  - A4 验证逻辑：验证 Agent 声明的 capabilities 是否在运行时可用（对比 `Identity.declare()` 与能力注册表）
  - A5 验证逻辑：检查认证链是否完整（Agent 启动时是否验证上游身份，是否存在代理认证路径）
  - 引用宪法中 A2-A5 的定义（`constraints.md` §A2-A5）
  - 更新 `arcnode/scripts/INDEX.md` 注册新脚本

  **Must NOT do**:
  - 不修改现有 S/T/R/G 约束脚本
  - A3 仅做静态日志字段检查（运行时追踪在 Phase 3 T16 实现）
  - A5 不嵌入任何实际的认证逻辑（仅验证"存在"认证链声明）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: A2-A5 涉及 Agent 安全、追踪、能力和认证，需要深刻理解 Agent 运行时架构
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T8, T9, T11, T12)
  - **Blocks**: T13
  - **Blocked By**: T1（需要 arcnode 验证脚本框架就绪）

  **References**:
  **Pattern References**:
  - `arcnode/scripts/validate-S1-safety.sh` — 标准验证脚本模板
  - `arcnode/scripts/validate-T2-timing.sh` — 时间相关验证模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` §A2-A5 — 约束定义
  - `agentmesh/packages/engine/src/governance/guardian.ts` — 安全治理参考

  **Test References**:
  - `arcnode/tests/validate-S1.test.sh` — 测试模式

  **Why Each Reference Matters**:
  - `validate-T2-timing.sh`：时间相关验证的模式参考（A3 的执行追踪需要时间戳验证）
  - `guardian.ts`：Agent 安全治理的运行时参考，A2/A5 的验证逻辑应与运行时行为一致

  **Acceptance Criteria**:
  - [ ] `validate-A2-agent-safety.sh` 文件存在且可执行
  - [ ] `validate-A3-agent-execution-trace.sh` 文件存在且可执行
  - [ ] `validate-A4-agent-capability.sh` 文件存在且可执行
  - [ ] `validate-A5-agent-auth-chain.sh` 文件存在且可执行
  - [ ] `arcnode validate --constraint A2` 返回 exit code 0（合法 Agent 安全配置）
  - [ ] `arcnode validate --constraint A3` 返回 exit code 0（追踪日志格式合规）
  - [ ] `arcnode validate --constraint A4` 返回 exit code 0（能力声明与注册表一致）
  - [ ] `arcnode validate --constraint A5` 返回 exit code 0（认证链完整）
  - [ ] INDEX.md 已更新注册四个新脚本

  **QA Scenarios**:

  ```
  Scenario: A2 Agent 安全配置验证
    Tool: Bash (arcnode)
    Preconditions: Agent 有安全配置（超时、SIGTERM 处理）
    Steps:
      1. 创建 /tmp/agent-safe/ 包含 valid timeout 和 signal handler 配置
      2. 运行 arcnode validate --constraint A2 --agent-dir /tmp/agent-safe/
      3. 检查 exit code 为 0
    Expected Result: exit code 0, 输出 "A2 PASS — safe termination configured"
    Failure Indicators: exit code 非 0 或安全配置检测遗漏
    Evidence: .omo/evidence/task-10-a2-pass.txt

  Scenario: A3 执行追踪日志字段检查
    Tool: Bash (arcnode)
    Preconditions: Agent 日志包含 session_id 和时间戳
    Steps:
      1. 创建 /tmp/agent-trace/logs/ 包含合法的追踪日志
      2. 运行 arcnode validate --constraint A3 --log-dir /tmp/agent-trace/logs/
      3. 检查日志字段（session_id, timestamp）完整
    Expected Result: exit code 0, 输出 "A3 PASS"
    Failure Indicators: exit code 1 或字段检测忽略
    Evidence: .omo/evidence/task-10-a3-pass.txt

  Scenario: A4 能力声明与运行时一致性
    Tool: Bash (arcnode)
    Preconditions: Agent 声明了 capabilities 并注册到能力注册表
    Steps:
      1. 创建 /tmp/agent-cap-declare/ 包含 capabilities 声明文件
      2. 运行 arcnode validate --constraint A4 --agent-dir /tmp/agent-cap-declare/
      3. 检查声明的能力是否在注册表中可用
    Expected Result: exit code 0, 输出 "A4 PASS — capabilities consistent"
    Failure Indicators: exit code 1（声明的能力不可用）
    Evidence: .omo/evidence/task-10-a4-pass.txt

  Scenario: A5 认证链完整性
    Tool: Bash (arcnode)
    Preconditions: 代理认证链有声明
    Steps:
      1. 创建 /tmp/agent-auth/ 包含上游身份声明和中间 Agent 列表
      2. 运行 arcnode validate --constraint A5 --agent-dir /tmp/agent-auth/
      3. 检查认证链是否完整声明
    Expected Result: exit code 0, 输出 "A5 PASS"
    Failure Indicators: exit code 1（声明不完整）
    Evidence: .omo/evidence/task-10-a5-pass.txt
  ```

  **Commit**: YES (groups with T8, T9, T11, T12)
  - Message: `feat(arcnode): add A2-A5 agent constraint validation scripts`
  - Files: `arcnode/scripts/validate-A2-agent-safety.sh`, `arcnode/scripts/validate-A3-agent-execution-trace.sh`, `arcnode/scripts/validate-A4-agent-capability.sh`, `arcnode/scripts/validate-A5-agent-auth-chain.sh`, `arcnode/scripts/INDEX.md`
  - Pre-commit: `arcnode validate --constraint A2 && arcnode validate --constraint A3 && arcnode validate --constraint A4 && arcnode validate --constraint A5`

---

## Phase 2 Detailed Tasks (Continued)

---

- [x] 11. A6-A8 Agent 约束验证脚本

  **What to do**:
  - 在 `arcnode/scripts/` 创建 `validate-A6-agent-resource-isolation.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-A7-agent-context-integrity.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-A8-agent-resource-accounting.sh` 验证脚本
  - A6 验证逻辑：检查 Agent 是否在隔离的环境中运行（验证容器/进程隔离声明、工作目录隔离、文件系统沙箱）
  - A7 验证逻辑：验证 Agent 的上下文是否纯净（无跨 Agent 上下文泄露、session_id 隔离、数据分区声明）
  - A8 验证逻辑：检查 Agent 资源核算（40% 初步实现）：验证 `pricing_config.yaml` 存在且包含 cost_per_token/cost_per_usage，不验证具体数值
  - 引用宪法中 A6-A8 的定义（`constraints.md` §A6-A8）
  - 更新 `arcnode/scripts/INDEX.md` 注册新脚本

  **Must NOT do**:
  - A6 不做实际的运行时隔离检测（仅验证隔离声明存在）
  - A8 仅做配置存在性检查（完整的资源核算在 T7 的统一模型之上）
  - 不修改现有 S/T/R/G 约束脚本

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: A6-A8 涉及资源隔离、上下文完整性和资源核算，需要深入理解 Agent 沙箱架构
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T8, T9, T10, T12)
  - **Blocks**: T13
  - **Blocked By**: T1

  **References**:
  **Pattern References**:
  - `arcnode/scripts/validate-S1-safety.sh` — 标准验证脚本模板
  - `arcnode/scripts/validate-T5-dependency-levels.sh` — 依赖级别验证（类似隔离级别）

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` §A6-A8 — 约束定义
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — 资源核算协议

  **Why Each Reference Matters**:
  - `validate-T5-dependency-levels.sh`：隔离级别的验证模式与 A6 的资源隔离逻辑相似
  - `constraints.md` §A6-A8：约束的权威定义源

  **Acceptance Criteria**:
  - [ ] `validate-A6-agent-resource-isolation.sh` 文件存在且可执行
  - [ ] `validate-A7-agent-context-integrity.sh` 文件存在且可执行
  - [ ] `validate-A8-agent-resource-accounting.sh` 文件存在且可执行
  - [ ] `arcnode validate --constraint A6` 返回 exit code 0（有隔离声明）
  - [ ] `arcnode validate --constraint A7` 返回 exit code 0（上下文隔离合规）
  - [ ] `arcnode validate --constraint A8` 返回 exit code 0（定价配置存在）
  - [ ] INDEX.md 已更新注册三个新脚本

  **QA Scenarios**:

  ```
  Scenario: A6 资源隔离声明检查
    Tool: Bash (arcnode)
    Preconditions: Agent 有隔离声明
    Steps:
      1. 创建 /tmp/agent-isolated/ 包含 isolation.yaml
      2. 运行 arcnode validate --constraint A6 --agent-dir /tmp/agent-isolated/
      3. 检查隔离声明格式
    Expected Result: exit code 0, 输出 "A6 PASS"
    Failure Indicators: exit code 1
    Evidence: .omo/evidence/task-11-a6-pass.txt

  Scenario: A7 上下文完整性检查
    Tool: Bash (arcnode)
    Preconditions: Agent 有上下文隔离配置
    Steps:
      1. 创建 /tmp/agent-context/ 包含 context_partition.yaml
      2. 运行 arcnode validate --constraint A7 --agent-dir /tmp/agent-context/
      3. 检查上下文分区声明
    Expected Result: exit code 0, 输出 "A7 PASS"
    Failure Indicators: exit code 1
    Evidence: .omo/evidence/task-11-a7-pass.txt

  Scenario: A8 资源核算配置存在性
    Tool: Bash (arcnode)
    Preconditions: 已部署 T7 的统一定价配置
    Steps:
      1. 运行 arcnode validate --constraint A8 --project-dir /path/to/project
      2. 检查 pricing_config.yaml 是否存在
    Expected Result: exit code 0, 输出 "A8 PASS"
    Failure Indicators: exit code 1
    Evidence: .omo/evidence/task-11-a8-pass.txt
  ```

  **Commit**: YES (groups with T8-T10, T12)
  - Message: `feat(arcnode): add A6-A8 agent constraint validation scripts`
  - Files: `arcnode/scripts/validate-A6-agent-resource-isolation.sh`, `arcnode/scripts/validate-A7-agent-context-integrity.sh`, `arcnode/scripts/validate-A8-agent-resource-accounting.sh`, `arcnode/scripts/INDEX.md`
  - Pre-commit: `arcnode validate --constraint A6 && arcnode validate --constraint A7 && arcnode validate --constraint A8`

- [x] 12. A9-A10 Agent 约束验证脚本

  **What to do**:
  - 在 `arcnode/scripts/` 创建 `validate-A9-agent-authorization-isolation.sh` 验证脚本
  - 在 `arcnode/scripts/` 创建 `validate-A10-agent-idempotency.sh` 验证脚本
  - A9 验证逻辑：检查 Agent 授权是否独立于调用方（验证 Agent 使用自身身份而非调用方身份执行操作、授权与认证分离声明）
  - A10 验证逻辑：验证 Agent 操作是否支持幂等性（存在 idempotency_key 字段、检查重复操作检测声明）
  - 引用宪法中 A9-A10 的定义（`constraints.md` §A9-A10）
  - 更新 `arcnode/scripts/INDEX.md` 注册新脚本

  **Must NOT do**:
  - A9 不做运行时授权检查（仅验证声明存在）
  - A10 不做实际的幂等重放检测（仅验证幂等设计声明）
  - 不修改现有 S/T/R/G 约束脚本

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: A9-A10 涉及授权隔离和幂等性，是 Agent 治理中最复杂的约束层级
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T8, T9, T10, T11)
  - **Blocks**: T13
  - **Blocked By**: T1

  **References**:
  **Pattern References**:
  - `arcnode/scripts/validate-S1-safety.sh` — 标准验证脚本模板
  - `arcnode/scripts/validate-T2-timing.sh` — 幂等性涉及时间维度

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` §A9-A10 — 约束定义

  **Why Each Reference Matters**:
  - `validate-T2-timing.sh`：A10 幂等性验证可能涉及请求 ID 时间窗口，与时间验证相关
  - `constraints.md` §A9-A10：约束的权威定义源

  **Acceptance Criteria**:
  - [ ] `validate-A9-agent-authorization-isolation.sh` 文件存在且可执行
  - [ ] `validate-A10-agent-idempotency.sh` 文件存在且可执行
  - [ ] `arcnode validate --constraint A9` 返回 exit code 0（授权隔离声明存在）
  - [ ] `arcnode validate --constraint A10` 返回 exit code 0（幂等性声明存在）
  - [ ] INDEX.md 已更新注册两个新脚本

  **QA Scenarios**:

  ```
  Scenario: A9 授权隔离声明检查
    Tool: Bash (arcnode)
    Preconditions: Agent 有授权隔离声明
    Steps:
      1. 创建 /tmp/agent-authz/ 包含 authorization.yaml
      2. 运行 arcnode validate --constraint A9 --agent-dir /tmp/agent-authz/
      3. 检查授权隔离格式
    Expected Result: exit code 0, 输出 "A9 PASS"
    Failure Indicators: exit code 1
    Evidence: .omo/evidence/task-12-a9-pass.txt

  Scenario: A10 幂等性声明检查
    Tool: Bash (arcnode)
    Preconditions: Agent 操作有幂等性设计声明
    Steps:
      1. 创建 /tmp/agent-idempotent/ 包含 idempotency.yaml
      2. 运行 arcnode validate --constraint A10 --agent-dir /tmp/agent-idempotent/
      3. 检查幂等性声明
    Expected Result: exit code 0, 输出 "A10 PASS"
    Failure Indicators: exit code 1
    Evidence: .omo/evidence/task-12-a10-pass.txt
  ```

  **Commit**: YES (groups with T8-T11)
  - Message: `feat(arcnode): add A9-A10 agent constraint validation scripts`
  - Files: `arcnode/scripts/validate-A9-agent-authorization-isolation.sh`, `arcnode/scripts/validate-A10-agent-idempotency.sh`, `arcnode/scripts/INDEX.md`
  - Pre-commit: `arcnode validate --constraint A9 && arcnode validate --constraint A10`

- [x] 13. CI集成 — arcnode约束验证加入pre-commit钩子

  **What to do**:
  - 在项目根目录创建/更新 `.husky/pre-commit` 钩子（或等价的 `package.json` scripts `precommit` 脚本）
  - 在 pre-commit 中添加 `arcnode validate --all`
  - 如果项目使用 `husky`：在 `.husky/pre-commit` 中添加 `npx arcnode validate --changed`
  - 如果项目不使用 husky：在 `package.json` 中添加 `"precommit": "arcnode validate --changed"` 并使用 `lint-staged`
  - 定义 `arcnode validate --changed` 标志：仅验证与 git staged 文件相关的约束（增量验证）
  - 添加 CI 配置文件（`.github/workflows/constraint-validation.yml`）用于 PR 检查
  - CI 配置：在 PR 时运行 `arcnode validate --all`，输出结果到 PR 注释

  **Must NOT do**:
  - 不破坏现有 pre-commit 钩子（如已存在的 lint/test）
  - 不使用 husky 之外的重型 git hook 框架
  - CI 不阻塞紧急修复（可跳过）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: CI/钩子集成是模式化操作，需理解现有 CI 配置约定
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖 T8-T12 的验证脚本先就绪）
  - **Parallel Group**: Wave 4 (after T8-T12)
  - **Blocks**: T17
  - **Blocked By**: T8, T9, T10, T11, T12

  **References**:
  **Pattern References**:
  - `.husky/pre-commit` — 现有 pre-commit 钩子（如存在）
  - `package.json` — scripts 段中的 precommit 定义
  - `.github/workflows/` — 现有 CI 工作流模式

  **Why Each Reference Matters**:
  - 现有 pre-commit 钩子：新验证必须附加在现有钩子后，不可替代
  - CI 工作流：模式必须与现有工作流兼容

  **Acceptance Criteria**:
  - [ ] `.husky/pre-commit` 或等价钩子包含 `arcnode validate --changed`
  - [ ] `.github/workflows/constraint-validation.yml` 文件存在
  - [ ] 运行 `git commit` 时自动触发 arcnode 验证
  - [ ] PR 创建时 CI 运行 `arcnode validate --all`（非阻塞）

  **QA Scenarios**:

  ```
  Scenario: Pre-commit 钩子自动验证
    Tool: Bash (git)
    Preconditions: 已有 .husky/pre-commit 配置
    Steps:
      1. 创建违反 A1 约束的临时文件
      2. 运行 git add && git commit -m "test" 2>&1 | tee /tmp/precommit-output.txt
      3. 检查输出是否包含 arcnode 验证调用
    Expected Result: commit 被阻止或输出中包含 "A1 FAIL"
    Failure Indicators: commit 静默通过（验证未触发）
    Evidence: .omo/evidence/task-13-precommit-block.txt

  Scenario: CI PR 验证
    Tool: Bash (git/gh)
    Preconditions: .github/workflows/constraint-validation.yml 已配置
    Steps:
      1. 创建包含合法变更的 PR
      2. 检查 CI 运行日志
      3. 验证 arcnode validate --all 在 CI 中运行
    Expected Result: CI 运行成功，输出 "arcnode validate: ALL PASS"
    Failure Indicators: CI 未触发或验证脚本不运行
    Evidence: .omo/evidence/task-13-ci-pass.txt
  ```

  **Commit**: YES
  - Message: `ci: integrate arcnode constraint validation into pre-commit and CI pipeline`
  - Files: `.husky/pre-commit`, `.github/workflows/constraint-validation.yml`, `package.json`
  - Pre-commit: `arcnode validate --changed`

---

## Phase 3 — Observability 可观测 (Sprint 5, Wave 7-8)

---

- [x] 14. EG5 相位锁定机制 — 运行时实现

  **What to do**:
  - 在 `agentmesh/packages/engine/src/` 创建 `phase-lock/` 模块
  - 实现 `PhaseLock` 接口：`lock(phaseId, agentId, duration)`, `unlock(phaseId, agentId)`, `isLocked(phaseId)`, `getCurrentPhase(agentId)`
  - 实现 `PhaseLockManager`：管理跨 Agent 的相位状态转换
  - 状态机：INIT → LOCKED → ACTIVE → RELEASED → EXPIRED
  - 集成到现有的 `GovernanceCoordinator` 治理流程中
  - 添加单元测试覆盖：正常相位转换、重复锁定拒绝、过期自动释放、并发冲突
  - EG5 的 arcnode 验证脚本已经在 T9 中创建，此任务实现运行时逻辑

  **Must NOT do**:
  - 不修改 Guardian/AnomalyRuleEngine 的核心逻辑
  - 不引入分布式锁的外部依赖（使用内存锁 + 超时机制）
  - 不破坏 T9 的 EG5 验证脚本接口

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 相位锁定是 Agent 协作的核心机制，需要深刻理解 Agent 生命周期和状态机设计
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖 T5-T6 的 pipeline 输入能力）
  - **Parallel Group**: Wave 5 (after T5, T6)
  - **Blocks**: T17
  - **Blocked By**: T5, T6

  **References**:
  **Pattern References**:
  - `agentmesh/packages/engine/src/governance/governance-coordinator.ts` — 治理协调器模式
  - `agentmesh/packages/engine/src/identity/` — 身份管理模块模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` §EG5 — 相位锁定约束定义
  - `~/Documents/学习进化/基建架构/机制/MECH-05-任务分解Wave模型.md` — Wave 模型中的相位概念

  **Why Each Reference Matters**:
  - `governance-coordinator.ts`：相位锁定必须与现有治理流程集成
  - MECH-05：相位锁定的业务来源，实现必须与机制定义一致

  **Acceptance Criteria**:
  - [ ] `phase-lock/` 模块文件存在
  - [ ] `PhaseLockManager` 支持 lock/unlock/isLocked/getCurrentPhase
  - [ ] 相位状态机正确转换：INIT → LOCKED → ACTIVE → RELEASED → EXPIRED
  - [ ] 重复锁定返回 `PhaseLockError.PHASE_ALREADY_LOCKED`
  - [ ] 过期自动释放（超时后 isLocked 返回 false）
  - [ ] `bun test packages/engine/src/phase-lock/` 全部通过
  - [ ] `arcnode validate --constraint EG5` 返回 exit code 0（运行时锁生效，T9 脚本升级验证）

  **QA Scenarios**:

  ```
  Scenario: 正常相位锁定与释放
    Tool: Bash (bun test)
    Preconditions: agentmesh 项目可构建
    Steps:
      1. 创建 PhaseLockManager 实例
      2. 调用 lock("phase-1", "agent-alpha", duration=5000)
      3. 调用 isLocked("phase-1") → 返回 true
      4. 调用 unlock("phase-1", "agent-alpha")
      5. 调用 isLocked("phase-1") → 返回 false
    Expected Result: lock → true, isLocked → true → unlock → isLocked → false
    Failure Indicators: isLocked 状态不对或 unlock 失败
    Evidence: .omo/evidence/task-14-phase-lock-normal.txt

  Scenario: 重复锁定拒绝
    Tool: Bash (bun test)
    Preconditions: PhaseLockManager 实例就绪
    Steps:
      1. 调用 lock("phase-1", "agent-alpha", 5000)
      2. 调用 lock("phase-1", "agent-beta", 5000)
      3. 检查是否抛出 PhaseLockError
    Expected Result: 第二次 lock 抛出错误，phase-1 仍由 alpha 持有
    Failure Indicators: 第二次 lock 静默覆盖或返回 true
    Evidence: .omo/evidence/task-14-phase-lock-contention.txt

  Scenario: 相位过期自动释放
    Tool: Bash (bun test)
    Preconditions: PhaseLockManager 实例就绪
    Steps:
      1. 调用 lock("phase-1", "agent-alpha", duration=10ms)
      2. 等待 20ms
      3. 调用 isLocked("phase-1")
    Expected Result: isLocked 返回 false（自动释放）
    Failure Indicators: isLocked 仍然返回 true（未过期）
    Evidence: .omo/evidence/task-14-phase-lock-expiry.txt
  ```

  **Commit**: YES
  - Message: `feat(pipeline): implement EG5 phase locking mechanism`
  - Files: `agentmesh/packages/engine/src/phase-lock/`, `agentmesh/packages/engine/src/__tests__/phase-lock/`
  - Pre-commit: `bun test packages/engine/src/phase-lock/ && arcnode validate --constraint EG5`

- [x] 15. 约束合规仪表板

  **What to do**:
  - 创建一个简单的 Web 仪表板，可视化 arcnode 约束合规状态
  - 技术栈：可选（推荐纯静态 HTML/JS，最小依赖）
  - 仪表板功能：显示所有 42 条约束的当前状态（PASS/FAIL/UNKNOWN），按类别排列（S/T/R/G/EG/A）
  - 读取 `arcnode/scripts/` 下所有验证脚本的执行结果（从 `arcnode validate --json` 输出解析）
  - 实现简单的 JSON API 终结点让前端获取最新的验证结果
  - 如果现有的 dashboard/agentmesh dashboard 可以扩展，优先复用
  - 添加红色/绿色状态指示器，支持过滤

  **Must NOT do**:
  - 不添加用户登录/认证功能（仅本地/内网使用）
  - 不使用重型前端框架（React/Vue 等），除非已存在
  - 不引入外部数据库

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 需要前端 UI 和可视化能力
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES（与 T14, T16 无依赖）
  - **Parallel Group**: Wave 5 (with T14, T16)
  - **Blocks**: T17
  - **Blocked By**: T7（需要统一定价数据展示）

  **References**:
  **Pattern References**:
  - `arcnode/scripts/INDEX.md` — 所有验证脚本列表
  - 项目现有 dashboard 目录（如存在）

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` — 42 条约束完整定义

  **Why Each Reference Matters**:
  - INDEX.md：仪表板必须注册所有可用脚本
  - constraints.md：约束分类（S/T/R/G/EG/A）决定仪表板的布局结构

  **Acceptance Criteria**:
  - [ ] 仪表板 HTML 文件存在（或集成到现有 dashboard）
  - [ ] 显示所有 42 条约束的合规状态
  - [ ] 按类别分组（S/T/R/G/EG/A）
  - [ ] 状态指示器（绿色/红色/灰色）
  - [ ] 支持过滤（按类别/状态）
  - [ ] JSON API 可返回最新验证结果

  **QA Scenarios**:

  ```
  Scenario: 仪表板加载并显示约束状态
    Tool: Bash (curl/WebFetch)
    Preconditions: 仪表板已部署在本地端口
    Steps:
      1. 访问仪表板 URL
      2. 检查页面是否加载
      3. 验证页面包含约束分组和状态指示器
    Expected Result: 仪表板显示 42 条约束，按 S/T/R/G/EG/A 分组
    Failure Indicators: 页面空白、加载失败或缺少约束分组
    Evidence: .omo/evidence/task-15-dashboard-load.txt
  ```

  **Commit**: YES
  - Message: `feat(dashboard): add constraint compliance visualization`
  - Files: `dashboard/` 或等价目录
  - Pre-commit: `curl http://localhost:PORT/ && echo "dashboard up"`

- [x] 16. Pipeline编排可观测性

  **What to do**:
  - 在 `agentmesh/packages/engine/src/` 创建 `observability/` 模块
  - 实现 Pipeline 执行追踪钩子：`PipelineTracer` 类
  - 追踪能力：记录每个 pipeline 步骤的开始/结束/持续时间/状态/输入摘要/输出摘要
  - 暴露可观测性数据：通过已有的 `GovernanceCoordinator` 或独立 JSON 端点
  - 确保与 T5-T6 的 `--pipeline-input`/`--pipeline-output` 数据格式一致
  - 与 T14 的 `PhaseLockManager` 集成：追踪相位锁定的转换事件
  - 添加单元测试

  **Must NOT do**:
  - 不引入外部 APM/监控依赖（OpenTelemetry 等）
  - 不修改现有的 pipeline 执行核心逻辑（仅添加钩子）
  - 追踪数据不包含敏感内容（身份认证信息等）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解 Pipeline 执行流程和可观测性设计模式
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES（与 T14 共享依赖，互不阻塞）
  - **Parallel Group**: Wave 5 (with T14, T15)
  - **Blocks**: T17
  - **Blocked By**: T5, T6

  **References**:
  **Pattern References**:
  - `agentmesh/packages/engine/src/identity/identity-manager.ts` — 模块创建模式
  - `agentmesh/packages/engine/src/governance/governance-coordinator.ts` — 治理集成模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — pipeline:json 协议
  - `~/Documents/学习进化/基建架构/机制/MECH-03-管线编排.md` — Pipeline 协议 v1.0

  **Why Each Reference Matters**:
  - `interface_contract.md`：追踪的字段必须与 pipeline:json schema 一致
  - MECH-03：管线编排机制定义，可观测性钩子必须反映实际编排流程

  **Acceptance Criteria**:
  - [ ] `observability/` 模块文件存在
  - [ ] `PipelineTracer` 能记录 pipeline 步骤的 start/end/duration/status
  - [ ] 可观测性数据可通过 JSON 端点获取
  - [ ] 数据格式与 pipeline:json schema 一致
  - [ ] `bun test` 全部通过

  **QA Scenarios**:

  ```
  Scenario: Pipeline 执行被正确追踪
    Tool: Bash (bun test)
    Preconditions: agentmesh 项目可构建
    Steps:
      1. 运行包含 3 个步骤的 pipeline
      2. 查询 PipelineTracer 的追踪记录
      3. 检查是否有 3 条追踪记录，包含 start/end/duration/status
    Expected Result: 3 条追踪记录，每条包含完整时间信息
    Failure Indicators: 记录缺失、缺少时间字段或状态不对
    Evidence: .omo/evidence/task-16-pipeline-trace.txt

  Scenario: 追踪数据 JSON 格式可消费
    Tool: Bash (curl)
    Preconditions: engine 运行中，有可观测性端点
    Steps:
      1. 访问 /observability/pipelines 端点
      2. 检查返回 JSON 格式
      3. 验证字段与 pipeline:json schema 对齐
    Expected Result: 返回格式良好的 JSON，包含必要追踪字段
    Failure Indicators: JSON 格式错误或缺少关键字段
    Evidence: .omo/evidence/task-16-trace-json.txt
  ```

  **Commit**: YES (groups with T14)
  - Message: `feat(pipeline): add orchestration observability hooks`
  - Files: `agentmesh/packages/engine/src/observability/`, `agentmesh/packages/engine/src/__tests__/observability/`
  - Pre-commit: `bun test packages/engine/src/observability/`

---

## Phase 4 — Hardening 硬化 (Sprint 6, Wave 9-10)

---

- [x] 17. 端到端集成测试

  **What to do**:
  - 创建 `tests/integration/` 目录，编写完整的端到端集成测试
  - 测试场景 1：A1 身份声明 → arcnode 验证 → agentmesh 运行时 → 全链路
  - 测试场景 2：pipeline:json 协议 → ontoderive 消费 → eidos 编排 → 全管线
  - 测试场景 3：EG1-EG6 全部验证脚本执行 → `arcnode validate --all` 全部通过
  - 测试场景 4：A2-A10 全部验证脚本执行 → `arcnode validate --all` 全部通过
  - 测试场景 5：相位锁定 → 发布 → 端到端治理流程
  - 测试场景 6：跨项目定价一致性 → 三个项目的 pricing_config 一致
  - 每个测试场景使用 `bun test` 或 `pytest` 框架，输出整洁的测试报告

  **Must NOT do**:
  - 不模拟外部服务（所有测试在本地运行）
  - 不测试与外部 LLM API 的集成
  - 不引入新的测试框架（复用项目现有框架）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 端到端测试需要理解所有 Phase 1-3 的交付物及其交互关系
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖所有 Phase 1-3 任务完成）
  - **Parallel Group**: Wave 6 (after T14, T15, T16)
  - **Blocks**: F1-F4
  - **Blocked By**: T13, T14, T15, T16

  **References**:
  **Pattern References**:
  - `agentmesh/packages/engine/src/__tests__/` — 现有测试模式
  - `arcnode/tests/` — 现有验证测试模式

  **API/Type References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` — 全部 42 条约束
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — 全部 11 种协议

  **Why Each Reference Matters**:
  - 测试场景必须覆盖宪法定义的全部约束和协议
  - 测试模式必须与项目现有测试风格一致

  **Acceptance Criteria**:
  - [ ] `tests/integration/` 目录存在
  - [ ] 场景 1-6 全部编写完成
  - [ ] `bun test tests/integration/` 全部通过
  - [ ] `arcnode validate --all` 返回全部 PASS
  - [ ] 跨项目定价一致性测试通过

  **QA Scenarios**:

  ```
  Scenario: 全约束验证通过
    Tool: Bash (arcnode)
    Preconditions: 所有 Phase 1-3 任务已完成并部署
    Steps:
      1. 运行 arcnode validate --all
      2. 检查每个约束的输出
    Expected Result: S1-S8, T1-T7, R1-R6, G1-G5, EG1-EG6, A1-A10 全部 PASS
    Failure Indicators: 任何约束 FAIL
    Evidence: .omo/evidence/task-17-all-validate-pass.txt

  Scenario: 完整管线端到端测试
    Tool: Bash (CLI pipeline)
    Preconditions: ontoderive、eidos、agentmesh 均可运行
    Steps:
      1. ontoderive derive --pipeline-output /tmp/e2e-pipeline.json
      2. eidos orchestrate --pipeline-input /tmp/e2e-pipeline.json
      3. arcnode validate --constraint A1
    Expected Result: 三步全部成功
    Failure Indicators: 任何一步失败
    Evidence: .omo/evidence/task-17-e2e-pipeline.txt
  ```

  **Commit**: YES
  - Message: `test(integration): end-to-end constraint pipeline integration tests`
  - Files: `tests/integration/`
  - Pre-commit: `bun test tests/integration/ && arcnode validate --all`

- [x] 18. 宪法更新 — 注册新约束

  **What to do**:
  - 更新 `~/Documents/学习进化/基建架构/宪法/constraints.md` 文件
  - 注册 EG1-EG6 到宪法约束表中（添加到 §Engineering Governance）
  - 注册 A1-A10 到宪法约束表中（添加到 §Agent Constraints）
  - 每个新约束的条目信息：ID、名称、类型、MUST/SHOULD 级别、验证脚本路径、生效日期
  - 更新 `interface_contract.md` 中的 pipeline:json 协议为正式版本（从草案状态）
  - 更新宪法文档的修订历史（版本号和日期）

  **Must NOT do**:
  - 不修改现有 S/T/R/G 约束的语义
  - 不修改宪法 §1-§8 核心条款
  - 不创建新的宪法文件（仅更新现有文件）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 文档更新任务，格式明确，内容已全量确定
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（需要 T17 验证后确保约束可注册）
  - **Parallel Group**: Wave 6 (after T17)
  - **Blocks**: T19
  - **Blocked By**: T8, T9, T10, T11, T12

  **References**:
  **Pattern References**:
  - `~/Documents/学习进化/基建架构/宪法/constraints.md` — 现有约束表的格式和结构
  - `~/Documents/学习进化/基建架构/宪法/interface_contract.md` — 协议文档

  **Why Each Reference Matters**:
  - constraints.md 的现有格式：新约束必须匹配现有表结构和命名规范

  **Acceptance Criteria**:
  - [ ] constraints.md 中包含 EG1-EG6 的注册条目
  - [ ] constraints.md 中包含 A1-A10 的注册条目
  - [ ] 每个条目包含：ID/名称/类型/级别/脚本路径/日期
  - [ ] pipeline:json 标记为正式版本
  - [ ] 修订历史已更新

  **QA Scenarios**:

  ```
  Scenario: 新约束注册完整性检查
    Tool: Bash (grep)
    Preconditions: constraints.md 已更新
    Steps:
      1. grep "EG1" constraints.md — 应该存在
      2. grep "A10" constraints.md — 应该存在
      3. grep -c "MUST" constraints.md — 比对期望值
    Expected Result: EG1 和 A10 都出现在文档中
    Failure Indicators: 缺少任何新约束条目
    Evidence: .omo/evidence/task-18-constraints-registered.txt
  ```

  **Commit**: YES (groups with T19)
  - Message: `docs(constitution): register EG1-EG6 and A1-A10 constraints`
  - Files: `~/Documents/学习进化/基建架构/宪法/constraints.md`, `~/Documents/学习进化/基建架构/宪法/interface_contract.md`
  - Pre-commit: `grep "EG1" constraints.md && grep "A10" constraints.md`

- [x] 19. 文档同步 — wiki/story 更新

  **What to do**:
  - 更新 Workspace 根目录的 AGENTS.md：添加 EG1-EG6 和 A1-A10 到治理定义
  - 更新文档 wiki 中的 ONTOLOGY.md：添加新约束类型定义
  - 更新 RULES.md：添加新约束的简要规则说明
  - 更新 INDEX.md 中的约束索引表
  - 确保所有新验证脚本在 arcnode 的 INDEX.md 中注册
  - 与 T18 配合，确保宪法文档和项目文档一致

  **Must NOT do**:
  - 不创建重复的文档（每个信息只在一个文件中维护）
  - 不修改核心宪法 §1-§8 内容
  - 不添加 AI slop 如"这是一个重要的里程碑"类空话

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 纯文档同步任务，需要保持文档风格一致
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖 T18 先完成宪法注册）
  - **Parallel Group**: Wave 6 (after T18)
  - **Blocks**: None（最后任务）
  - **Blocked By**: T18

  **References**:
  **Pattern References**:
  - `~/Documents/学习进化/基建架构/AGENT.md` — 现有治理定义格式
  - `~/Documents/学习进化/基建架构/ONTOLOGY.md` — 本体定义格式
  - `~/Documents/学习进化/基建架构/RULES.md` — 规则说明格式

  **Why Each Reference Matters**:
  - 文档必须与现有格式一致，保持统一的文档体系

  **Acceptance Criteria**:
  - [ ] AGENTS.md 包含 EG1-EG6 和 A1-A10 的治理定义
  - [ ] ONTOLOGY.md 包含新约束类型
  - [ ] RULES.md 包含新约束的简要规则
  - [ ] INDEX.md 约束索引已更新
  - [ ] arcnode/scripts/INDEX.md 已注册所有新验证脚本

  **QA Scenarios**:

  ```
  Scenario: 文档一致性检查
    Tool: Bash (grep)
    Preconditions: 所有文档已更新
    Steps:
      1. grep "EG1" AGENTS.md
      2. grep "A10" AGENTS.md
      3. grep "pipeline:json" interface_contract.md
    Expected Result: EG1/A10 出现在 AGENTS.md 中，pipeline:json 出现在 interface_contract.md
    Failure Indicators: 任何新约束在文档中缺失
    Evidence: .omo/evidence/task-19-docs-consistency.txt
  ```

  **Commit**: YES
  - Message: `docs(wiki): update ONTOLOGY/AGENT/RULES with new constraints`
  - Files: `~/Documents/学习进化/基建架构/AGENT.md`, `~/Documents/学习进化/基建架构/ONTOLOGY.md`, `~/Documents/学习进化/基建架构/RULES.md`, `arcnode/scripts/INDEX.md`
  - Pre-commit: `grep "EG1" AGENTS.md && grep "A10" AGENTS.md`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
- [x] F2. **Code Quality Review** — `unspecified-high`
- [x] F3. **Real Manual QA** — `unspecified-high`
- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Phase 1**: 
  - T1: `feat(arcnode): add A1 agent identity validation constraint` — arcnode/
  - T2: `docs(pipeline): add pipeline:json protocol specification` — 宪法/interface_contract.md
  - T3: `feat(agentmesh): implement A1 agent identity declaration runtime` — packages/engine/src/identity/
  - T4: `feat(sharedbrain): bridge A1 identity to AgentRole model` — organs/
  - T5: `feat(ontoderive): implement --pipeline-input consumer` — ontoderive/
  - T6: `feat(eidos): implement --pipeline-input consumer for编排器` — eidos/
  - T7: `feat(resource): unify pricing model across agentmesh/SharedBrain/MetaOS` — shared/

- **Phase 2**:
  - T8-T12: `feat(arcnode): add EG1-EG3/EG4-EG6/A2-A5/A6-A8/A9-A10 validation scripts` — arcnode/scripts/
  - T13: `ci: add arcnode constraint validation to pre-commit hooks` — .husky/, package.json

- **Phase 3**:
  - T14: `feat(pipeline): implement EG5 phase locking mechanism` — packages/engine/src/phase-lock/
  - T15: `feat(dashboard): add constraint compliance visualization` — dashboard/
  - T16: `feat(pipeline): add orchestration observability hooks` — packages/engine/src/observability/

- **Phase 4**:
  - T17: `test(integration): end-to-end constraint pipeline integration` — tests/integration/
  - T18: `docs(constitution): register EG1-EG6 and A1-A10 constraints` — 宪法/constraints.md
  - T19: `docs(wiki): update ONTOLOGY/AGENT/RULES with new constraints` — 基建架构/

---

## Success Criteria

### Verification Commands
```bash
# Phase 1 验证
arcnode validate --constraint A1                    # 预期: PASS
ontoderive --pipeline-input test-pipeline.json     # 预期: 正确消费并输出
eidos orchestrate --pipeline-input test-pipeline.json  # 预期: 正确消费并编排

# Phase 2 验证
arcnode validate --constraint EG1                 # 预期: PASS
arcnode validate --constraint EG6                 # 预期: PASS
arcnode validate --constraint A1                  # 预期: PASS
arcnode validate --constraint A10                 # 预期: PASS

# Phase 3 验证
arcnode validate --constraint EG5                  # 预期: PASS (含相位锁定)

# Phase 4 验证
bun test --all                                    # 预期: 全部通过
arcnode validate --all                            # 预期: 全部PASS
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] A1身份声明在3个项目中一致
- [ ] pipeline:json在3个工具中可消费
- [ ] EG1-EG6验证通过
- [ ] A2-A10验证通过
- [ ] Resource定价统一
- [ ] Phase锁定正确执行