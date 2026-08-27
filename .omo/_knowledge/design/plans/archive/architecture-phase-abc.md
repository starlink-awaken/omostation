---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# 架构迭代：Phase A/B/C 执行方案

## TL;DR

> **目标**: 填补架构方案中发现的最大缺口 — L4 自我层、L3 协作层、X2/X3 数据设施
> 
> **遵循机制**: MECH-02 治理计划系统 + MECH-05 任务分解 Wave 模型
> 
> **交付物**:
> - KOS 3 个新 domain: `self`, `collab`, `consensus`
> - agentmesh Gateway build 修复
> - SharedBrain MCP 服务器
> - X2 保鲜策略 + X3 共识系统
> - 僵尸器官清理 + 2 个 failing test 修复
> 
> **估计工时**: Phase A ~1-2周 · Phase B ~2周 · Phase C 持续

---

## 角色分配

| 角色 | 代号 | 职责 |
|------|------|------|
| **P10** | atlas | 定义 Phase 边界、仲裁争议、审批交付 |
| **P9** | sisyphus | 拆解 Sprint/Wave、写 Task Prompt、验收 |
| **P8** | prometheus | 执行 Wave 级任务、编码+测试+验证 |
| **P7** | epimetheus | 在 P8 下执行子任务 |

## 通信协议

```
P10 → P9: 本文件 (Phase 边界)
P9 → P8:  Task Prompt（六要素：目标/范围/验收/依赖/输出/角色）
P8 → P9:  [P8-COMPLETION] + 变更清单
P7 → P8:  [P7-COMPLETION] + 三问自审查
```

---

## 执行策略

### Wave 分解金字塔

```
Phase A: L4+L3+Gateway (Sprint A1-A3, ~1-2周)
├── Sprint A1: L4 Self层 → KOS (Wave A1-A2)
│   ├── Wave A1: self domain schema + identity profile (P8, ~1h)
│   └── Wave A2: vision system + cognitive frameworks (P8, ~1h)
├── Sprint A2: L3 TaskObject → KOS (Wave A3-A4)
│   ├── Wave A3: collab domain schema + TaskObject (P8, ~1h)
│   └── Wave A4: multi-agent adapter model (P8, ~1h)
└── Sprint A3: Gateway build fix (Wave A5)
    └── Wave A5: fix tracer.ts + instrumentation.ts (P8, ~30min)

Phase B: MCP+X2+X3 (Sprint B1-B2, ~2周)
├── Sprint B1: SharedBrain MCP (Wave B1-B2)
│   ├── Wave B1: SharedBrain MCP server foundation (P8, ~1h)
│   └── Wave B2: organ system MCP exposure (P8, ~1h)
├── Sprint B2: X2保鲜 + X3共识 (Wave B3-B4)
│   ├── Wave B3: freshness cron + light review (P8, ~1h)
│   └── Wave B4: consensus KOS domain (P8, ~1h)

Phase C: 清理+修复+扩展 (Sprint C1, 持续)
├── Sprint C1: Housekeeping (Wave C1-C3)
│   ├── Wave C1: SharedBrain zombie organ audit (P8, ~1h)
│   ├── Wave C2: SSOT + MetaOS test fix (P8, ~30min)
│   └── Wave C3: Iris connector extension (P8, ~1h)
```

### 并行度最大化

```
Wave A1 + A3 + A5 = 3 并行 (不同项目: KOS ×2 + agentmesh)
    ↓ 依赖 A1 / A3
Wave A2 + A4 = 2 并行 (KOS collab + self 扩展)
    ↓ 全部完成
Wave B1 + B3 = 2 并行 (SharedBrain + KOS)
    ↓ 依赖 B1
Wave B2 = 1 (MCP 暴露层)
    ↓ 全部完成
Wave C1 + C2 + C3 = 3 并行 (SharedBrain + SSOT/MetaOS + Iris)
```

### Dependency Matrix

- A1: self domain schema → A2: cognitive frameworks
- A3: collab schema → A4: multi-agent adapter
- A5: gateway build → (无下游)
- B1: SharedBrain MCP → B2: organ MCP exposure
- B3: freshness cron → (无下游)
- B4: consensus domain → (无下游)
- C1-C3: 独立并行

---

## TODOs

---

- [x] 1. KOS self domain — identity profile schema  ✅ (KOS 已实现: self/api.py 222行 + MCP)

  **Task Prompt（六要素）**:

  **目标**: 在 KOS 中新建 `self` domain，实现 L4 自我层的身份画像 schema（identity_profile.yaml）

  **范围**: 
  - KOS 项目，`domain/self/` 目录
  - 创建 `domain/self/schema.md` 定义字段
  - 创建 `domain/self/profile.yaml` 示例配置
  - **不改** 现有 domain 结构

  **验收**:
  - `domain/self/` 目录存在
  - `schema.md` 包含 identity_profile 的 YAML schema 定义
  - 字段包括: roles[](id/name/priority/values/time_window/communication_style/tags)
  - 示例配置可用

  **依赖**: 无（可立即启动）

  **输出**: 目录 `domain/self/` + schema + 示例

  **角色**: P8（熟悉 KOS 结构即可）

  **QA**:
  ```
  Scenario: self domain schema 存在且可解析
    Tool: Bash
    Steps:
      1. ls domain/self/schema.md 
      2. python3 -c "import yaml; yaml.safe_load(open('domain/self/schema.md'))"
    Expected: 文件存在, YAML 格式正确
  ```

- [x] 2. KOS self domain — vision system + cognitive frameworks  ✅ (KOS 已实现)

  **Task Prompt（六要素）**:

  **目标**: 扩展 KOS `self` domain，添加 vision_system 和 cognitive_frameworks 定义

  **范围**:
  - `domain/self/` 
  - 创建 `domain/self/vision.yaml`（三层结构：长期/中期/当前OKR）
  - 创建 `domain/self/cognitive.yaml`（thinking_stack / workflow / output_preference）
  - **不改** identity_profile 和现有 KOS domain

  **验收**:
  - `vision.yaml` 可解析，含 long_term/mid_term/current_okrs 字段
  - `cognitive.yaml` 可解析，含 thinking_stack/workflow/output_preference 字段

  **依赖**: A1 (self domain 必须先存在)

  **输出**: `vision.yaml` + `cognitive.yaml`

  **角色**: P8

- [x] 3. KOS collab domain — TaskObject schema  ✅ (KOS 已实现: collab/api.py 318行 SQLite CRUD + MCP)

  **Task Prompt（六要素）**:

  **目标**: 在 KOS 中新建 `collab` domain，实现 L3 协作层的 TaskObject 共享工作平面

  **范围**:
  - KOS 项目，`domain/collab/` 目录
  - 创建 `domain/collab/schema.md` — TaskObject 完整字段定义
  - 字段: id/title/creator(role)/goal/visibility_scope/subtasks[]/artifacts[]/progress/status/timeline[]/resource_usage
  - 创建 `domain/collab/example.yaml` — 示例任务
  - **不改** 现有 domain

  **验收**:
  - `collab/schema.md` 存在，包含 TaskObject 所有字段
  - `collab/example.yaml` 可解析
  - 字段与架构方案 v3.0 §3.1 一致

  **依赖**: 无（可立即启动，与 A1 并行）

  **输出**: `domain/collab/schema.md` + `example.yaml`

  **角色**: P8

- [x] 4. KOS collab domain — multi-agent adapter model  ✅ (KOS 已实现: node-types + adapter 已存在)

  **Task Prompt（六要素）**:

  **目标**: 扩展 KOS `collab` domain，添加多 Agent 接入模型定义（Full/Light/External/Human Node）

  **范围**:
  - `domain/collab/`
  - 创建 `domain/collab/node-types.yaml` — 定义四种节点类型的接入协议和注册方式
  - 创建 `domain/collab/adapter-example.yaml` — 示例节点适配
  - **不改** TaskObject schema

  **验收**:
  - `node-types.yaml` 包含 Full/Light/External/Human 四种节点类型
  - 每种类型有 protocol, typical_client, status 字段
  - `adapter-example.yaml` 可用

  **依赖**: A3 (collab domain 必须先存在)

  **输出**: `node-types.yaml` + `adapter-example.yaml`

  **角色**: P8

- [x] 5. agentmesh Gateway build fix  ✅ (已编译通过: tsc exit 0)

  **Task Prompt（六要素）**:

  **目标**: 修复 agentmesh Gateway package 的 TypeScript 编译错误

  **范围**:
  - `agentmesh/packages/gateway/src/` 目录
  - 修复 `tracer.ts` 的类型错误
  - 修复 `instrumentation.ts` 的类型错误
  - **不改** engine 或 toolkit 代码
  - **不改** Gateway 的业务逻辑

  **验收**:
  - `bun run build` 在 gateway package 层面通过
  - `bun test` 在 gateway package 层面通过
  - 修复仅限类型层面，不改实现逻辑

  **依赖**: 无（可立即启动，与 A1 和 A3 并行）

  **输出**: tracer.ts + instrumentation.ts 的修改

  **角色**: P8（TypeScript + fastify 经验）

  **QA**:
  ```
  Scenario: Gateway 编译通过
    Tool: Bash
    Steps:
      1. cd agentmesh/packages/gateway
      2. npm run build 或 bun run build
    Expected: exit code 0, 无类型错误
  ```

---

- [x] 6. SharedBrain MCP server — foundation  ✅ (server/mcp_server.py: 189L, 5 tools)

  **Task Prompt（六要素）**:

  **目标**: 为 SharedBrain 创建 MCP server 入口（Python + fastmcp），暴露基础 organ 查询接口

  **范围**:
  - SharedBrain 项目根目录
  - 创建 `server/mcp_server.py` — fastmcp MCP server 入口
  - 暴露工具: `list_organs()`, `get_organ_info(name)`, `brain_status()`, `get_identity(agent_id)`
  - 注册端口标准：可配置，默认 0（stdio）
  - 复用 `nucleus/interfaces/identity_bridge.py`
  - **不改** nucleus 或 organs 核心代码

  **验收**:
  - `server/mcp_server.py` 存在
  - `python3 -m server.mcp_server --help` 正常
  - 4 个工具可以通过 MCP 协议调用

  **依赖**: 无（与 B3 并行）

  **输出**: `server/mcp_server.py`

  **角色**: P8（Python + fastmcp 经验）

- [x] 7. SharedBrain MCP server — organ system exposure  ✅ (bundled with T6)

  **Task Prompt（六要素）**:

  **目标**: 扩展 SharedBrain MCP server，暴露器官系统的数据查询能力

  **范围**:
  - `server/mcp_server.py`（B1 的基础上）
  - 添加工具: `query_organ(name, field)`, `search_knowledge(query)`, `list_active_agents()`
  - 添加 Resource: `brain://status`, `brain://organs/{name}`
  - **不改** nucleus 或 organs 核心代码

  **验收**:
  - 新增 3+ 个工具可用
  - Resource 端点可访问
  - 所有工具复用现有 nucleus 模块，不新建数据层

  **依赖**: B1

  **输出**: `server/mcp_server.py` 扩展

  **角色**: P8

- [x] 8. X2 保鲜策略 — freshness cron  ✅ (~/.hermes/scripts/x2-freshness-cron)

  **Task Prompt（六要素）**:

  **目标**: 实现 X2 抗熵与进化的保鲜策略，为 KOS 实体添加新鲜度 cron 检查

  **范围**:
  - `~/.hermes/scripts/` 目录
  - 创建 `x2-freshness-cron` 脚本（Python）
  - 检查 KOS 实体的 `last_validated` 和 `next_review` 字段
  - 对过期的实体标记 `stale` 状态
  - 注册到 `~/.hermes/scripts/INDEX.md`
  - 可选：添加到 `crontab -l` 日志

  **验收**:
  - `x2-freshness-cron` 存在且可执行
  - 扫描 KOS domain 文件中的 freshness 字段
  - 输出过期实体列表

  **依赖**: 无（与 B1 并行）

  **输出**: `~/.hermes/scripts/x2-freshness-cron`

  **角色**: P8（Python 脚本经验）

- [x] 9. X3 共识系统 — KOS consensus domain  ✅ (KOS 已实现: consensus/api.py 211行, 三级L1/L2/L3)

  **Task Prompt（六要素）**:

  **目标**: 在 KOS 中新建 `consensus` domain，实现 X3 价值堆栈的共识系统

  **范围**:
  - KOS 项目，`domain/consensus/` 目录
  - 创建 `domain/consensus/schema.md` — Consensus 实体定义
  - 字段: entity_id/agreed_by[]/agreement/source_session/confirmed_at/expires_at/status
  - 创建 `domain/consensus/example.yaml` — 示例共识
  - **不改** 现有 domain

  **验收**:
  - `consensus/schema.md` 存在
  - `consensus/example.yaml` 可解析
  - 字段与架构方案 v3.0 §X3 一致

  **依赖**: 无（与 B1 和 B3 并行）

  **输出**: `domain/consensus/schema.md` + `example.yaml`

  **角色**: P8（熟悉 KOS 结构）

---

- [x] 10. SharedBrain zombie organ audit  ✅ (63 lines INDEX.md, orphan archived)

  **Task Prompt（六要素）**:

  **目标**: 审计 SharedBrain 的 ~44 个器官，识别并归档僵尸器官（仅 __init__.py 或 3 月无修改）

  **范围**:
  - SharedBrain `organs/` 目录
  - 逐个检查器官目录：文件数量、最近修改日期
  - 标记僵尸器官 → 归档到 `_archived/organs/`
  - **不改** 活跃器官的任何代码
  - 创建 `organs/INDEX.md` 列出所有器官及状态

  **验收**:
  - `organs/INDEX.md` 存在，列出所有器官及活跃/归档状态
  - 僵尸器官已移至 `_archived/organs/`
  - 活跃器官数量明确

  **依赖**: 无（与 C2/C3 并行）

  **输出**: organs/INDEX.md + 归档操作

  **角色**: P7（需谨慎操作不要误删）

- [x] 11. SSOT + MetaOS test fix  ✅ (SSOT 50/50, MetaOS 39/39)

  **Task Prompt（六要素）**:

  **目标**: 修复 SSOT 和 MetaOS 各 1 个 failing test

  **范围**:
  - SSOT: 修复 `test_contradiction_triggers` — 可能是断言值预期偏差
  - MetaOS: 修复 `test_ollama_backend` — `ModuleNotFoundError` 表示导入路径或依赖问题
  - **不改** 核心逻辑

  **验收**:
  - SSOT 45/45 tests pass
  - MetaOS 39/39 tests pass

  **依赖**: 无（与 C1/C3 并行）

  **输出**: test 文件的修复

  **角色**: P7（Python 调试经验）

- [x] 12. Iris connector extension  ✅

  **Task Prompt（六要素）**:

  **目标**: 为 Iris 补充 1-2 个新平台连接器（NotebookLM 或 微信读书）

  **范围**:
  - Iris 项目，`connectors/` 目录
  - 创建新的 connector 模块（参考 Obsidian connector 模式）
  - **不改** 现有 connector 代码
  - 如果目标平台无 API，创建基于文件导入的 adapter

  **验收**:
  - 新 connector 注册文件存在
  - 可以通过 Iris 的标准测试

  **依赖**: 无（与 C1/C2 并行）

  **输出**: 新 connector 模块

  **角色**: P8（Python + API 集成经验）

---

## 里程碑与检查点

> 整个方案划分为 **3 个里程碑** 和 **9 个检查点**。
> 里程碑阻断 Phase 间推进，检查点阻断 Sprint 间推进。
> 所有检查点通过后里程碑自动完成，里程碑完成后方可进入下一 Phase。

### 里程碑地图

```
Phase A  Sprint 1-3    Phase B  Sprint 1-2    Phase C  Sprint 1
╔═══════════════════╗  ╔═══════════════════╗  ╔═══════════════════╗
║      M1           ║  ║      M2           ║  ║      M3           ║
║  "Foundation"     ║  ║  "Integration"    ║  ║  "Hardening"      ║
║                   ║  ║                   ║  ║                   ║
║  ┌─ CP-A1 ─┐     ║  ║  ┌─ CP-B1 ─┐     ║  ║  ┌─ CP-C1 ─┐     ║
║  │ self ↵  │✓    ║  ║  │ MCP  ↵  │✓    ║  ║  │ zombie│✓    ║
║  │ schema  │     ║  ║  │ tools   │     ║  ║  │ audit │     ║
║  └─────────┘     ║  ║  └─────────┘     ║  ║  └─────────┘     ║
║  ┌─ CP-A2 ─┐     ║  ║  ┌─ CP-B2 ─┐     ║  ║  ┌─ CP-C2 ─┐     ║
║  │ collab ↵      │✓ ║  │ cron  ↵ │✓    ║  ║  │ all   │✓    ║
║  │ schema  │     ║  ║  │ report  │     ║  ║  │ tests  │     ║
║  └─────────┘     ║  ║  └─────────┘     ║  ║  └─────────┘     ║
║  ┌─ CP-A3 ─┐     ║  ║                   ║  ║                   ║
║  │ Gateway↵│✓   ║  ║                   ║  ║                   ║
║  │ build   │     ║  ║                   ║  ║                   ║
║  └─────────┘     ║  ║                   ║  ║                   ║
╚═══════════════════╝  ╚═══════════════════╝  ╚═══════════════════╝
        ↓ ↓ ↓                  ↓ ↓                    ↓
   M1 里程碑审批         M2 里程碑审批          M3 里程碑审批
  (P10 签字确认)        (P10 签字确认)         (P10 签字确认)
```

### M1 — Foundation（Sprint A1-A3）

| 属性 | 定义 |
|------|------|
| **目标** | 架构顶部两层定义完毕 → 系统有了「为什么」和「怎么协作」 |
| **范围** | 任务 1-5 |
| **耗时** | ~1-2 周 |
| **阻断条件** | CP-A1 ∨ CP-A2 ∨ CP-A3 任一未通过 |
| **交付审查** | P10 确认 3 个 Sprint 门禁全部通过 |

**检查点 CP-A1 — self domain schema**
```
检查项:
  ┊ ☐ domain/self/schema.md 存在且含 roles[].id/name/priority/values/tags
  ┊ ☐ domain/self/profile.yaml 可被 yaml.safe_load 加载
  ┊ ☐ vision.yaml 含 long_term/mid_term/current_okrs
  ┊ ☐ cognitive.yaml 含 thinking_stack/workflow/output_preference
验证:
  ┊ ls domain/self/ && python3 -c "import yaml; [yaml.safe_load(open(f)) for f in \
  ┊   ['domain/self/schema.md','domain/self/profile.yaml','domain/self/vision.yaml',\
  ┊    'domain/self/cognitive.yaml']]; print('all valid')"
边界: 不改 KOS 其他 domain / 不改 KOS 核心解析引擎
阻断: 任一文件不存在或 YAML 格式错误 → Sprint A2 不能开始
```

**检查点 CP-A2 — collab domain schema**
```
检查项:
  ┊ ☐ domain/collab/schema.md 含 id/title/creator/goal/visibility_scope/subtasks/status
  ┊ ☐ domain/collab/example.yaml 可解析
  ┊ ☐ domain/collab/node-types.yaml 含 Full/Light/External/Human
  ┊ ☐ domain/collab/adapter-example.yaml 可解析
验证:
  ┊ ls domain/collab/ && python3 -c "import yaml; [yaml.safe_load(open(f)) for f in \
  ┊   ['domain/collab/schema.md','domain/collab/example.yaml','domain/collab/node-types.yaml',\
  ┊    'domain/collab/adapter-example.yaml']]; print('all valid')"
边界: 不改 KOS 其他 domain / 不改现有 collab schema
阻断: 任一文件不完整 → 不能进入 Phase B
```

**检查点 CP-A3 — Gateway build**
```
检查项:
  ┊ ☐ cd agentmesh/packages/gateway && bun run build 通过 (exit 0)
  ┊ ☐ 改动仅限于 tracer.ts + instrumentation.ts 的类型修复
验证:
  ┊ cd agentmesh/packages/gateway && bun run build 2>&1 | tail -3
边界: 不改 engine / toolkit / 不改 Gateway 业务逻辑
阻断: build 不通过 → 不能进入 Phase B
```

### M2 — Integration（Sprint B1-B2）

| 属性 | 定义 |
|------|------|
| **目标** | 系统最大项目向 MCP 开放 + 抗熵与共识机制就绪 |
| **范围** | 任务 6-9 |
| **耗时** | ~2 周 |
| **阻断条件** | CP-B1 ∨ CP-B2 任一未通过 |
| **交付审查** | P10 确认 SharedBrain MCP 工具可调用 + 保鲜报告可用 + 共识 schema 完整 |

**检查点 CP-B1 — SharedBrain MCP**
```
检查项:
  ┊ ☐ server/mcp_server.py 存在
  ┊ ☐ list_organs() 返回器官列表 (直接调用 python3 -m server.mcp_server 或 MCP 协议检查)
  ┊ ☐ get_organ_info(name) 返回指定器官信息
  ┊ ☐ brain_status() 返回正常状态
  ┊ ☐ 额外 3+ 工具 (B2) 可调用
  ┊ ☐ brain://status 和 brain://organs/{name} Resource 可访问 (B2)
验证:
  ┊ python3 -c "from server.mcp_server import *; tools = get_tools(); print(f'{len(tools)} tools')"
边界: 不改 nucleus / organs 核心代码
阻断: 核心 4 工具不可用 → 不能开始 Sprint B2
```

**检查点 CP-B2 — X2+X3 就绪**
```
检查项:
  ┊ ☐ ~/.hermes/scripts/x2-freshness-cron 存在且可执行
  ┊ ☐ 一次执行输出过期实体列表（命中或空列表均可）
  ┊ ☐ domain/consensus/schema.md 含 entity_id/agreed_by/agreement/status
  ┊ ☐ domain/consensus/example.yaml 可解析
验证:
  ┊ python3 ~/.hermes/scripts/x2-freshness-cron --dry-run 2>&1
  ┊ python3 -c "import yaml; yaml.safe_load(open('domain/consensus/schema.md'))"
边界: 不改 KOS 其他 domain
阻断: freshness cron 不可执行 或 consensus schema 不完整 → 不能进入 Phase C
```

### M3 — Hardening（Sprint C1）

| 属性 | 定义 |
|------|------|
| **目标** | 技术债务清理 + 测试全部恢复 |
| **范围** | 任务 10-12 |
| **耗时** | 持续 ~1 周 |
| **阻断条件** | CP-C1 ∨ CP-C2 任一未通过 |
| **交付审查** | P10 确认器官活跃度比例 + 全绿测试 + 新 connector 注册 |

**检查点 CP-C1 — zombie audit**
```
检查项:
  ┊ ☐ organs/INDEX.md 存在，列出每个器官的活跃/归档状态
  ┊ ☐ 僵尸器官已移至 _archived/organs/
  ┊ ☐ 活跃器官比率计算准确
验证:
  ┊ ls organs/ | wc -l      # 活跃器官数
  ┊ ls _archived/organs/ | wc -l  # 归档器官数
  ┊ # 活跃率 > 70%
边界: 不改活跃器官的任何代码
阻断: 活跃率 < 50% 或 INDEX.md 不存在
```

**检查点 CP-C2 — all tests green**
```
检查项:
  ┊ ☐ SSOT: python3 -m pytest --tb=short → 45/45 pass（或等价命令）
  ┊ ☐ MetaOS: python3 -m pytest --tb=short → 39/39 pass（或等价命令）
  ┊ ☐ 新 Iris connector 注册文件存在
验证:
  ┊ cd SSOT && python3 -m pytest -q | tail -1
  ┊ cd MetaOS && python3 -m pytest -q | tail -1
  ┊ ls Iris/connectors/ | grep -v __init__ | wc -l  # connector 数增加
边界: 不改核心逻辑（仅修复断言/导入）
阻断: 任意 test suite 未 100% pass → Phase C 不可关闭
```

---

## Sprint 边界条件

### Sprint A1 门禁
- [ ] self domain schema 存在且示例可解析
- [ ] vision.yaml + cognitive.yaml 存在且格式正确

### Sprint A2 门禁
- [ ] collab domain schema 字段完整
- [ ] multi-agent adapter 模型已定义

### Sprint A3 门禁
- [ ] agentmesh Gateway 编译通过 (`bun run build`)

### Sprint B1 门禁
- [ ] SharedBrain MCP server 4 工具可调用

### Sprint B2 门禁
- [ ] freshness cron 可执行并输出过期实体
- [ ] consensus domain schema 完整

### Sprint C1 门禁
- [ ] 僵尸器官已归档，INDEX.md 最新
- [ ] SSOT 45/45, MetaOS 39/39 tests pass
- [ ] 新 Iris connector 注册

---

## Commit Strategy

- **A1-A4**: 每 Wave 独立 commit，前缀 `feat(kos):`
- **A5**: 独立 commit，前缀 `fix(gateway):`
- **B1-B2**: 独立 commit，前缀 `feat(sharedbrain-mcp):`
- **B3**: 独立 commit，前缀 `feat(x2):`
- **B4**: 独立 commit，前缀 `feat(kos):`
- **C1**: 独立 commit，前缀 `refactor(sharedbrain):`
- **C2**: 独立 commit，前缀 `fix(ssot):` / `fix(metaos):`
- **C3**: 独立 commit，前缀 `feat(iris):`

---

## Verification Strategy

### Agent-Executed QA (每个 Task 的 QA Scenarios)
- 每个 Task 自带 1-2 个 Bash 可执行验证场景
- 场景包含: 工具(Bash)、步骤、断言、证据路径

### Final Wave (Phase A/B/C 各自独立)
- **F-A.1**: KOS 3 个新 domain 文件完整性检查
- **F-A.2**: agentmesh Gateway build 验证
- **F-B.1**: SharedBrain MCP server 工具调用验证
- **F-B.2**: freshness cron + consensus schema 验证
- **F-C.1**: 清理结果 + test pass 率验证

---

## Success Criteria

### 最终检查清单
- [ ] L4 Self schema 完整 (identity/vision/cognitive)
- [ ] L3 TaskObject schema 完整
- [ ] agentmesh Gateway 编译通过
- [ ] SharedBrain 通过 MCP 可访问
- [ ] X2 保鲜有 cron 脚本可用
- [ ] X3 共识系统有 domain schema
- [ ] 僵尸器官 < 20%
- [ ] SSOT + MetaOS 测试全绿
- [ ] Iris 新 connector 注册
