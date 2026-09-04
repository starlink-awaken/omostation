---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0191: Workspace × Documents 全域双平面架构与长期治理体系

- **Status**: Accepted
- **Date**: 2026-08-17
- **Author**: Architecture & Governance Team
- **Deciders**: Chief Architect, Virtual Board (B.D.S.K.)
- **Consulted**: ECOS, Runtime, Agora, Cockpit, L4-Kernel
- **Informed**: All Agents, All Domain Maintainers

---

## 1. 上下文与背景 (Context)

在 `omostation` 生态中，存在两大核心物理载体：
1. **`Workspace` (`~/Workspace`)**：工程代码仓库、子模块、微内核 (L4)、编译器 (MOF)、算力中枢 (omlxc/AetherForge)、执行与调度引擎 (Runtime)、CI 门禁与自动化基础设施。
2. **`Documents` (`~/Documents`)**：包含 `@公共`、`@驾驶舱`、`@工作文档/卫健委`、`@工作文档/国转中心`、`@学习进化`、`@家庭生活`、`@创意创作`、`@个人`、`@OPC` 等人类实际生活与业务领域的知识、事实、档案与内容资产。

### 历史核心痛点
- **运行时污染内容面 (Runtime/Cache Leakage)**：历史上，Agent 在 `Documents` 目录下直接编写 Python 脚本、安装 `node_modules`、启动本地 daemon，导致 `Documents` 散落多达 44,534+ 处运行时和缓存违规。
- **事实与状态的双重真源 (Dual-Truth Divergence)**：业务事实（如卫健委项目进度、家庭健康数据）与工程执行状态缺乏明确解耦，出现跨域裸写和数据状态冲突。
- **多客户端配置碎片化 (Client Configuration Drift)**：Claude Desktop、Zed、ZCode、Codex、ChatGPT 对 `Documents` 的 MCP 挂载缺乏统一声明式 SSOT。

---

## 2. 架构决策 (Decision)

### 2.1 双平面分离定律 (The Dual-Plane Separation Law)
- **内容与事实平面 (`Documents`)**：只负责 **What & Truth**。包含 Markdown 报告、YAML 结构化事实、PDF/图片归档。**严禁安装 Python/Node 环境，严禁落地可执行脚本，严禁生成构建缓存**。
- **工程与执行平面 (`Workspace`)**：只负责 **How & Compute**。包含所有的代码实现、CLI 工具、MCP Server、Launchd Plist 生成、CI 自动化门禁。
- **交互边界契约**：
  - Agent 在 `Documents` 域工作时，仅挂载只读受控的 `Cockpit Documents MCP`。
  - 跨域访问必须经由 `bos://{domain_id}/{resource}` 统一路由，严禁使用相对路径或绝对路径直读直写。

### 2.2 MOF 动态约束规则扩展 (E-DOC 规则集)

> ⚠️ **DESIGN-ONLY (not enforced)** — 2026-08-17 实测核实: E-DOC/ln-001~005 五条
> 规则仅存在于本 ADR 文本, MOF 规则引擎 (governance-checks registry) / CI /
> Agent Preflight 均无对应实现 (ln-005 部分除外: 生成工具存在但无强制门禁)。
> 证据见 `.omo/_knowledge/audits/2026-08-17-edoc-rules-effective-status.md`。
> 接线与否待人类排期 (T6-08 移交项 H, 决策 H2=标 DESIGN-ONLY 已执行)。
在 MOF L0 元模型中正式注册并编译以下核心架构红线：

1. **`E-DOC-001` [REQUIRED] (X4)**：禁止在 `Documents` 领域目录下直接创建可执行脚本文件（`.py`, `.sh`, `.bash`, `.js`, `.ts`, `.rb`, `.go`）。
2. **`E-DOC-002` [REQUIRED] (X4)**：禁止在 `Documents` 目录下引入任何依赖环境目录（`node_modules`, `.venv`, `__pycache__`, `.pytest_cache`）。
3. **`E-DOC-003` [REQUIRED] (X1)**：禁止跨域直接修改私有实体或元数据（DIP-02），跨域状态变更必须通过 `_signals/SIGNALS.md` 或 Agora 路由。
4. **`E-DOC-004` [REQUIRED] (X2)**：关键事实文件（`_entities/facts/*.yaml`）必须具备结构化 Schema 校验，且审查周期不得超过 14 天（保鲜门禁）。
5. **`E-DOC-005` [REQUIRED] (X1)**：多客户端（Claude, Zed, ZCode, Codex, ChatGPT）配置必须由 `bin/gac/documents-*-config.py` 从 `documents-domain-projects.yaml` 单一真源生成，严禁手工维护。

### 2.3 单次自愈范式 (Suggested Patch Recipes)
当 Agent 违反 `E-DOC` 规则时，MOF 拦截器必须在 Diagnostic Envelope 中返回可直接替换的修复建议：
- **违规**：在 `~/Documents/@工作文档/卫健委/sync_data.py` 写入脚本。
- **自愈**：将脚本重定向写入 `~/Workspace/scripts/weijian/sync_data.py`，并在 Documents 登记 SOP 声明。

---

## 3. 架构推演与影响分析 (Consequences & Trade-offs)

### 正向影响 (Positive)
1. **内容面纯净度提升至 100%**：彻底杜绝缓存膨胀与环境污染，使 Documents 可以安全进行 Git/iCloud/网盘多端无损同步。
2. **单一事实真源明确**：物理事实在 Documents，执行逻辑在 Workspace，两平面各司其职，消除双重真源冲突。
3. **客户端统一管控**：通过单一脚本生成所有 IDE 配置，消除 Agent 在不同工具下的感知差异。
4. **毫秒级防逃逸与自愈**：MOF Preflight 拦截器在内存级（$< 0.2\text{ms}$）拦截违规并提供直接补丁，保障开发流顺畅。

### 潜在成本与应对 (Mitigations)
- **Agent 工具受限感**：在 Documents 目录下 Agent 无法直接 `python run_test.py`。
  - *应对*：在 System Prompt 注入 `<documents_dual_plane_guardrails>`，前置告知 Agent 通过 Workspace CLI 或受控 MCP 工具执行任务。

---

## 4. 合规性与验证门禁 (Compliance & Verification)
- **静态扫描**：`ecos-constraint documents audit`
- **动态拦截**：`runtime_governance_preflight` 与 `AntiEscapeGuard`
- **CI 阻断**：`documents-domain-project-check.py` 与 `documents-content-plane-migration-check.py`
