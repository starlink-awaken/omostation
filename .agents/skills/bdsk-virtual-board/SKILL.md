---
name: bdsk-virtual-board
description: "B.D.S.K. 虚拟董事会 (Mode-A 深度辩论 / Mode-B 快速决策) 4角共识执行与本地 LLM 接入指南。当任意 Agent 面临架构设计、核心技术选型、重大代码修改或风险 ROI 决策时调用。"
---

# B.D.S.K. Virtual Board — 多角思维决策与数字副官操作体系

> **SSOT**: `.omo/_knowledge/bos-registry.json` (`bos://governance/board/execute`)  
> **ADR**: `0203-requirement-iteration-workflow-mandatory.md` / `W2 战略扩展`  
> **架构契约**: 结合“LLM=CPU, Agent=OS, MCP/BOS=硬件”第一性原理。

## 1. 触发场景 (When To Use)

在任意 Agent（包括 Claude Code、Cursor、Antigravity 及外部自研 Agent）处理以下任务时，**强制或建议激活**本技能：
- **系统架构或重大方案选型**：需在“快速落地 (MVP)”与“长期反脆弱性 (Risk & ROI)”之间寻找最佳平衡点。
- **高风险重构与关键路径修改**：涉及底层依赖、多子模块互操作、跨域通信协议变动。
- **长尾场景造物与深度方案创新**：需要从常规版、进阶版、疯狂版多个维度扩展产品竞争力。
- **敏感安全与合规审计**：在政务、医疗（医疗健康与公共卫生管理）、企业私有化部署前进行风控排查。

---

## 2. 4 角思维框架 (B.D.S.K. Persona Matrix)

通过支持 `@角色名` 语法或标准 API，任意 Agent 均可调取指定思维角色的决策视角：

| 角色标记 | 角色名称 | 核心思维 | 审查重点 (Checklist Focus) |
| :--- | :--- | :--- | :--- |
| **`@Builder`** | 🧑‍💻 建造者 / 技术合伙人 | **工程思维 (How & MVP)** | 模块化可复用性、最高人效比、落地路径最短、代码简洁清晰 |
| **`@Devil`** | ⚡️ 批判者 / 风控官 | **反脆弱思维 (Risk & ROI)** | 边界异常、合规风险、单点故障、运维技术债务、ROI 是否为正 |
| **`@Sage`** | 🧠 贤者 / 战略家 | **系统思维 (Context & Essence)** | 第一性原理、长期扩展性、架构对齐与解耦、生态领域定位 |
| **`@Keeper`** | 👁️ 守夜人 / 观察者 | **控制论思维 (Process & Memory)** | SSOT 真理一致性、执行与声明一致性、历史经验与教训回溯 |

### 议事流程 (Board Operational Modes)
- **模式 A (Mode-A, 深度决策)**：面向核心架构变动。进行 4 角轮流审议，输出最终权重评分与共识裁决建议。
- **模式 B (Mode-B, 快速迭代)**：面向敏捷开发与轻量功能。由指定的主力合伙人（通常为 `@Builder` 或 `@Devil`）执行精简一针见血判定。

---

## 3. 标准调用契约 (Interface Contracts)

### 3.1 BOS URI 服务路由 (BOS Endpoints)
上层智能体可以通过统一 BOS 总线访问虚拟董事会：
- **`bos://governance/board/execute`** (`domain: governance`)：直接提交提案及模式，返回董事会综合共识与执行路线。
- **`bos://persona/board/route`** (`domain: persona`)：解析 `@Builder` / `@Devil` / `@Sage` / `@Keeper` 语法，分发到对应角色的特定逻辑。

### 3.2 命令行工具接入 (CLI Quick-Start)
```bash
# 执行模式 A（深度 4 角辩论）
python -m cockpit.commands.runtime --board-mode A --topic "引入本地 LLM 协同的架构选型与风控评估"

# 针对单角逻辑快速诊断
python -m cockpit.commands.runtime --persona Devil --topic "分析项目直接推送 main 仓库的安全风险"
```

### 3.3 Python SDK 集成契约
```python
from runtime.board.board_engine import BoardConsensusEngine, PersonaRole

engine = BoardConsensusEngine(default_mode="A")
verdict = engine.deliberate(
    topic="新特性的系统级重构方案",
    context={"target_repo": "omostation", "security_level": "high"}
)
print(verdict.to_markdown())
```

---

## 4. AetherForge + OMLXC 本地与边缘算力协同架构 (Compute & LLM Integration)

根据**“LLM=CPU, Agent=OS, MCP/BOS=硬件”**架构体系，系统天然保持计算单元（CPU/LLM）的无状态与解耦。在需要**高机密数据主权（医疗/政企）**、**降低 4 角辩论高频 Token 成本**，或调用本地边缘计算时，应用层不可盲目重构推理后端或写死调用库，必须统一通过 **AetherForge (`projects/aetherforge`)** 算力框架与 **OMLXC (Omostation MLX Compute / Apple MLX Edge Client)** 进行路由与编排。

### 4.1 为什么要使用 AetherForge + OMLXC 接入算力 (First-Principles ROI)?
1. **统一网关与模型服务网格 (Gateway & Mesh)**：
   - AetherForge 作为“能力与算力框架”，天然承载 `gateway / mesh / swarm`。上层 B.D.S.K. 虚拟董事会无须感知底层物理推理节点是苹果 MLX 芯片、Ollama 还是大模型集群。
   - 杜绝散乱连接，通过服务网格路由进行并发负载均衡与故障剔除。
2. **安全与数据主权 (Air-gapped Compliance)**：
   - 处理政务与卫生脱敏数据、私有工程架构或处于物理隔绝无网环境时，通过本地 **omlxc / MLX 量化模型（或边缘算力集群）**提供推理，确保数据在本地闭环零外泄。
3. **云边协同与成本削减 (Cloud-Edge Hybrid Engine)**：
   - **边缘高频初审 (omlxc / Local Edge)**：绑定至 `@Builder` (代码草拟/语法扫描) 与 `@Devil` (边界漏洞与回归排查)，利用本地芯片高吞吐、零 API 计费的优势完成高频轮查。
   - **云端战略决断 (Cloud Authoritative)**：绑定至 `@Sage` (第一性原理与架构权衡) 与 `@Keeper` 终裁整合，用高参云端模型把关架构演进。

### 4.2 BOS 算力服务绑定契约 (BOS Compute URI)
AetherForge 已在系统真理库中正式注册以下协议接口（见 `projects/agora/etc/bos-services.yaml`）：
- **`bos://compute/aetherforge/infer`** (`domain: compute`)：统一通用推理接口，无缝转发 OpenAI Compatible 与 MLX JSON-RPC 调用。
- **`bos://compute/aetherforge/mesh`** (`domain: compute`)：算力服务网格拓扑发现与多模型负载均衡器。
- **`bos://compute/aetherforge/swarm`** (`domain: compute`)：多智能体并发群体决策及算力资源调度编排。

### 4.3 标准接入配置文件参考 (AetherForge Compute Config)
在 `projects/aetherforge` 与 B.D.S.K. 引擎的关联映射中，推荐声明以下计算拓扑（仅修改端点，不侵入业务逻辑）：
```yaml
llm_compute_units:
  local_omlxc_edge:
    provider: omlxc_mlx               # Apple MLX Client / Ollama OpenAI-compatible
    endpoint_uri: "bos://compute/aetherforge/infer"
    base_url: "http://127.0.0.1:8000/v1"
    default_model: "mlx-community/Qwen2.5-14B-Instruct-4bit"
    role_bindings: ["builder", "devil"]
    mesh_strategy: "latency_first"
  cloud_authoritative:
    provider: openai_compatible       # Cloud High-Param Authoritative
    endpoint_uri: "bos://compute/aetherforge/infer"
    base_url: "${ARK_ENDPOINT_URL}"
    default_model: "${ARK_MODEL_ID}"
    role_bindings: ["sage", "keeper"]
    mesh_strategy: "quality_first"
```

---

## 5. Agent 落地治理门禁 (Governance & Gate Compliance)

1. **不可绕过工作流 (ADR-0203)**：任何由 B.D.S.K. 决议通过的需求迭代方案，一旦涉及写文件的实施阶段，均必须启动标准的 agent-workflow（`start -> claim -> verify -> closeout`）。
2. **SSOT 不可变契约**：所有重大方案输出与实施说明均必须与文档 SSOT 契约对齐，执行 `make gac-local-gate` 门禁检查。
