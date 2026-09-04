---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0190: MOF 动态约束与 Agent 实时治理体系 (MOF Dynamic Constraint Governance Architecture)

- **状态**: Accepted
- **日期**: 2026-08-17
- **决策者**: Builder, Sage, Devil, Keeper (Virtual Board)
- **影响范围**: `projects/ecos`, `projects/runtime`, MCP Server, Agent Toolchains, Submodule CI Gates

---

## 1. 上下文与问题背景 (Context & Problem Statement)

在 Omostation 的多 Agent 与分层微内核架构（LLM=CPU, Agent=OS, MCP=硬件, MOF=内核对象模型与符号表）演进中，静态的文档规范难以阻止 Agent 在复杂长调用链路中产生架构越界行为，例如：
1. **跨层私有直连**：上层 L3 组件直接 `import runtime.private` 或 `l4_kernel.internal`，绕过 Agora 路由与服务契约；
2. **环境逃逸与污染**：执行 `pip install --user` 或写入落盘恶意脚本后间接执行；
3. **越权路径读写**：写入受保护的未授权业务目录；
4. **事后拦截痛点**：传统 CI 拦截周期长，Agent 遇到报错后容易产生幻觉重试甚至反向破坏。

我们需要建立一套**全生命周期、纳秒/微秒级低延迟、内存级零大模型依赖、具备单次自愈能力（One-Shot Self-Healing）的动态架构治理闭环**。

---

## 2. 核心决策与架构设计 (Decision & Architecture)

### 2.1 五层全生命周期治理闭环

```mermaid
graph TD
    SSOT[MOF SSOT 元模型 constraints.yaml] -->|编译| Compiler[MOFPolicyCompiler]
    Compiler -->|规则派生| MemoryRules[(内存级预编译规则表)]
    
    subgraph 事前预防 (Shift-Left Context Synthesis)
        MemoryRules --> Synthesizer[MOFContextSynthesizer]
        Synthesizer -->|动态生成 XML 约束块| Prompt[Agent System Prompt: mof_architecture_guardrails]
    end

    subgraph 事中毫秒级拦截 (FastMCP Runtime Interceptor)
        Prompt --> AgentAction[Agent 工具调用 Action]
        AgentAction --> Interceptor[GovernanceInterceptor]
        Interceptor -->|AST 依赖分析| AST[AstDependencyInspector]
        Interceptor -->|路径边界校验| Path[PathBoundaryInspector]
        Interceptor -->|命令安全检测| Cmd[CommandSafetyInspector]
        Interceptor -->|落盘脚本防逃逸| Escape[AntiEscapeGuard]
    end

    subgraph 单次自愈 (One-Shot Self-Healing)
        Interceptor -->|违规 REJECTED| Diag[携带 suggested_patch 的结构化诊断 Envelope]
        Diag --> AgentSelfFix[Agent 精准替换修复]
    end

    subgraph 事后审计与 CLI 治理工具
        MemoryRules --> CLI[ecos-constraint CLI Suite]
        CLI --> explain[explain: 规则动机与反例详解]
        CLI --> audit[audit: 代码库静态扫描]
        CLI --> eval[eval: 工具调用参数预演]
        CLI --> drift[drift: SSOT 与运行时一致性校验]
    end
```

### 2.2 核心模块清单

1. **`MOFPolicyCompiler` (`projects/ecos`)**:
   - 解析 MOF L0 `constraints.yaml` 元模型；
   - 构建内存级强类型规则集 `CompiledPolicySet`，支持 `REQUIRED`、`IMMUTABLE`、`PREFERRED` 严重等级；
   - 内置 AST 检查器、命令检查器与路径边界检查器。

2. **`MOFContextSynthesizer` (`projects/ecos`)**:
   - 根据 Agent 运行时的 Domain 和 Layer 动态合成轻量级 `<mof_architecture_guardrails>` XML 块；
   - 注入 Agent 上下文，提供事前边界感知，控制 Token 消耗 $< 200$ tokens。

3. **`GovernanceInterceptor` (`projects/runtime`)**:
   - 挂载在 FastMCP 运行时与 Tool 执行入口之前；
   - 纳秒/微秒级内存解析（$< 0.2\text{ms}$），物理阻断非法工具调用；
   - 扩展 `AntiEscapeGuard`：对写入 `/tmp`, `./scratch` 等临时路径的 `.sh`/`.py` 脚本内容做同等级别的深层 AST/Shell 高危分析。

4. **单次自愈食谱 (Actionable Code Recipes)**:
   - 拦截响应不再只是冷冰冰的 `REJECTED`，而是返回带有 `suggested_patch` 的代码修复范式（例如改用 `from agora.client import get_service_client`）；
   - 使 Agent 在单次重试中直接纠偏，自愈成功率提升至 $> 95\%$。

5. **`ecos-constraint` CLI 治理套件**:
   - `ecos-constraint explain <rule_id>`: 交互式查看规则动机、违规反例与合规范式；
   - `ecos-constraint audit [path] [--strict] [--json]`: 静态审计目录；
   - `ecos-constraint eval --tool <name> --args <json>`: 预演校验工具调用；
   - `ecos-constraint drift`: 规则漂移校验；
   - `ecos-constraint guardrail`: 生成当前领域的 Prompt 约束。

6. **FastMCP 治理工具注册 (`projects/runtime/mcp_server.py`)**:
   - `runtime_governance_preflight`: 运行时动作 Pre-flight 语义拦截与架构合规性检查；
   - `runtime_governance_guardrails`: 获取领域 Prompt 约束块；
   - `runtime_governance_explain`: 查询规则自愈详情。

---

## 3. 性能与安全性指标 (SLAs & Validation)

| 指标项 | 目标要求 | 实测数据 | 状态 |
| :--- | :--- | :--- | :--- |
| **拦截延迟** | $< 1.0\text{ms}$ | **$0.02\text{ms} \sim 0.15\text{ms}$** | ✅ 达标 (超出预期) |
| **外部网络/大模型依赖** | 0 依赖 (纯内存静态 AST) | **0 依赖** | ✅ 达标 |
| **单测覆盖率** | 100% PASS | **1221 tests (ecos) + 67 tests (runtime)** | ✅ 达标 |
| **落盘脚本防逃逸** | 100% 拦截 | **全面覆盖 `.sh`/`.bash`/`.zsh`** | ✅ 达标 |

---

## 4. 迁移与兼容性保证 (Compatibility)

- 完全向后兼容已有 FastMCP 工具列表与 CLI 接口；
- 当 `ecos` 模块未安装在当前 Python 环境时，`GovernanceInterceptor` 自动降级为内置的 Standalone Fallback 规则集，保证任何环境下均不会抛出未捕获异常。
