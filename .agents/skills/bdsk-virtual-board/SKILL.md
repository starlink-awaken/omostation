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

## 4. 本地 LLM (Local LLM / Air-gapped Edge) 协同接入架构

根据**“LLM=CPU, Agent=OS, MCP=硬件”**架构体系，系统天然保持计算单元（CPU/LLM）的无状态与解耦。在需要**高机密数据主权（医疗/政企）**或**降低 4 角辩论高频 Token 成本**时，适用以下选型策略：

### 4.1 为什么要接入本地 LLM (Why Local LLM)?
1. **安全与数据主权 (Air-gapped Compliance)**：在处理脱敏医疗数据、政企架构资产或审计网络中，纯本地局域网（Ollama / vLLM）运行，完全杜绝公有云数据传输风险。
2. **零成本的高频第一轮初审 (Cost-Free First-Pass Review)**：B.D.S.K. 的 4 角高频对话如果全部消耗外部高参数推理 API 将大幅增加开销。通过本地中等参数量模型（如 Qwen-2.5-14B / Llama-3.1-8B）作为 Builder 初稿与 Devil 漏洞预扫描机，成本几乎为零。
3. **云边双向混编 (Cloud-Edge Hybrid Engine)**：
   - ** Edge LLM (本地计算单元)**：绑定至 `@Builder` (代码构建) 与 `@Devil` (基础语法/边界挑刺)。
   - ** Cloud LLM (云端大推理单元)**：绑定至 `@Sage` (顶级架构权衡) 与终裁整合。

### 4.2 接入设计规范 (OpenAI Compatible Protocol)
- **拒绝专有 SDK 强耦合**：全部模型对接一律采用标准 `OpenAI Compatible REST API`。
- **默认端点配置建议**：
  ```yaml
  llm_compute_units:
    local_edge:
      provider: ollama
      base_url: "http://127.0.0.1:11434/v1"
      default_model: "qwen2.5:14b"
      role_bindings: ["builder", "devil"]
    cloud_authoritative:
      provider: openai_compatible
      base_url: "${ARK_ENDPOINT_URL}"
      default_model: "${ARK_MODEL_ID}"
      role_bindings: ["sage", "keeper"]
  ```

---

## 5. Agent 落地治理门禁 (Governance & Gate Compliance)

1. **不可绕过工作流 (ADR-0203)**：任何由 B.D.S.K. 决议通过的需求迭代方案，一旦涉及写文件的实施阶段，均必须启动标准的 agent-workflow（`start -> claim -> verify -> closeout`）。
2. **SSOT 不可变契约**：所有重大方案输出与实施说明均必须与文档 SSOT 契约对齐，执行 `make gac-local-gate` 门禁检查。
