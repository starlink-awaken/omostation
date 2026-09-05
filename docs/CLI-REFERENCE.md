---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-04
---

# Cockpit CLI 命令参考

> 自动生成于 1970-01-01T00:00:00Z | 源: cockpit.commands.registry (SSOT) + capability-registry.yaml
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

共 **210** 个命令条目。八大正交域: **governance**、**workflow**、**memory**、**compute**、**bus**、**scene**、**system**、**user**。

## 目录

- [🏛️ 治理 (Governance)](#治理-governance) (16 个命令)
- [👤 用户 (User)](#用户-user) (8 个命令)
- [📄 专项工具 (Domain)](#专项工具-domain) (12 个命令)
- [📋 项目 (Project)](#项目-project) (12 个命令)
- [📚 研究 (Research)](#研究-research) (9 个命令)
- [📡 通讯 (Messaging)](#通讯-messaging) (5 个命令)
- [📦 数据 (Data)](#数据-data) (3 个命令)
- [🔌 总线接入 (ECCP)](#总线接入-eccp) (1 个命令)
- [🖥️ 基础设施 (Infra)](#基础设施-infra) (11 个命令)
- [🛠️ 系统 (System)](#系统-system) (15 个命令)
- [🤖 Agent 协作](#agent-协作) (4 个命令)
- [🧠 知识引擎 (BOS)](#知识引擎-bos) (10 个命令)
- [遗留命令映射](#遗留命令映射) (45 个)
- [全局 Flags](#全局-flags)
- [MCP 工具映射](#mcp-工具映射)

---

## 🏛️ 治理 (Governance)

### `cockpit audit-ledger`

治理审计账本查询 (隐藏运维面)

**用法**:

```bash
cockpit audit-ledger [flags]
cockpit audit-ledger --json          # 机器可读输出
cockpit audit-ledger --dry-run       # 预检 (无副作用)
cockpit audit-ledger --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit bdsk`

B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演)

**用法**:

```bash
cockpit bdsk [flags]
cockpit bdsk --json          # 机器可读输出
cockpit bdsk --dry-run       # 预检 (无副作用)
cockpit bdsk --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit cards`

CARDS 卡片状态管理 (list / get / search / serve)

**用法**:

```bash
cockpit cards [flags]
cockpit cards --json          # 机器可读输出
cockpit cards --dry-run       # 预检 (无副作用)
cockpit cards --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit command-audit`

15 维命令评分卡管理 (init/validate/report/lint)

**用法**:

```bash
cockpit command-audit [flags]
cockpit command-audit --json          # 机器可读输出
cockpit command-audit --dry-run       # 预检 (无副作用)
cockpit command-audit --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit context`

显示系统上下文 (Phase / CARDS / 约束 / 引导)

**用法**:

```bash
cockpit context [flags]
cockpit context --json          # 机器可读输出
cockpit context --dry-run       # 预检 (无副作用)
cockpit context --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit controller-shadow`

读取 Runtime 旧控制器影子迁移回执

**用法**:

```bash
cockpit controller-shadow [flags]
cockpit controller-shadow --json          # 机器可读输出
cockpit controller-shadow --dry-run       # 预检 (无副作用)
cockpit controller-shadow --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit dlp-guard`

外发前防泄密扫描 (敏感识别+挂起+脱敏)

**用法**:

```bash
cockpit dlp-guard [flags]
cockpit dlp-guard --json          # 机器可读输出
cockpit dlp-guard --dry-run       # 预检 (无副作用)
cockpit dlp-guard --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit domain-status`

显示 Documents 域项目绑定与引导状态

**用法**:

```bash
cockpit domain-status [flags]
cockpit domain-status --json          # 机器可读输出
cockpit domain-status --dry-run       # 预检 (无副作用)
cockpit domain-status --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit facts-audit`

审计 Documents 文档域 facts 文件

**用法**:

```bash
cockpit facts-audit [flags]
cockpit facts-audit --json          # 机器可读输出
cockpit facts-audit --dry-run       # 预检 (无副作用)
cockpit facts-audit --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit facts-validation`

读取 Runtime Facts 审计回执

**用法**:

```bash
cockpit facts-validation [flags]
cockpit facts-validation --json          # 机器可读输出
cockpit facts-validation --dry-run       # 预检 (无副作用)
cockpit facts-validation --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit governance`

架构治理 (委派 arcnode-*)

**用法**:

```bash
cockpit governance [flags]
cockpit governance --json          # 机器可读输出
cockpit governance --dry-run       # 预检 (无副作用)
cockpit governance --help          # 完整参数面
```

  · 所属域: `🏛️ 架构与治理 (Governance, Contracts, GAC, Audits)`  |  成熟度: stable  |  风险: low

### `cockpit harness`

Harness 全生命周期合规 (trace/verify/gac/compliance/…)

**用法**:

```bash
cockpit harness [flags]
cockpit harness --json          # 机器可读输出
cockpit harness --dry-run       # 预检 (无副作用)
cockpit harness --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit mcp`

启动 MCP server 或列出工具

**用法**:

```bash
cockpit mcp [flags]
cockpit mcp --json          # 机器可读输出
cockpit mcp --dry-run       # 预检 (无副作用)
cockpit mcp --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit model-freshness`

读取 Runtime 模型新鲜度回执

**用法**:

```bash
cockpit model-freshness [flags]
cockpit model-freshness --json          # 机器可读输出
cockpit model-freshness --dry-run       # 预检 (无副作用)
cockpit model-freshness --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit policy`

⚖️ 领域监管合规与 Policy-as-Code 红线审查 (E-POL-*)

**用法**:

```bash
cockpit policy [flags]
cockpit policy --json          # 机器可读输出
cockpit policy --dry-run       # 预检 (无副作用)
cockpit policy --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low  |  委派目标: `ecos.cli.constraint policy`

### `cockpit sanyi-status`

读取 Runtime 三医状态一致性回执

**用法**:

```bash
cockpit sanyi-status [flags]
cockpit sanyi-status --json          # 机器可读输出
cockpit sanyi-status --dry-run       # 预检 (无副作用)
cockpit sanyi-status --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 👤 用户 (User)

### `cockpit completion`

生成 Shell 自动补全脚本 (bash/zsh/fish)

**用法**:

```bash
cockpit completion [flags]
cockpit completion --json          # 机器可读输出
cockpit completion --dry-run       # 预检 (无副作用)
cockpit completion --help          # 完整参数面
```

  · 所属域: `user`  |  成熟度: stable  |  风险: low

### `cockpit demo`

快速演示

**用法**:

```bash
cockpit demo [flags]
cockpit demo --json          # 机器可读输出
cockpit demo --dry-run       # 预检 (无副作用)
cockpit demo --help          # 完整参数面
```

  · 所属域: `user`  |  成熟度: stable  |  风险: low

### `cockpit docs`

CLI 参考手册生成与导出 (docs/CLI-REFERENCE.md)

**用法**:

```bash
cockpit docs [flags]
cockpit docs --json          # 机器可读输出
cockpit docs --dry-run       # 预检 (无副作用)
cockpit docs --help          # 完整参数面
```

  · 所属域: `user`  |  成熟度: stable  |  风险: low

### `cockpit help`

查看产品地图与快速入门

**用法**:

```bash
cockpit help [flags]
cockpit help --json          # 机器可读输出
cockpit help --dry-run       # 预检 (无副作用)
cockpit help --help          # 完整参数面
```

  · 所属域: `user`  |  成熟度: stable  |  风险: low

### `cockpit init`

🚀 初始化向导（同 quickstart）

**用法**:

```bash
cockpit init [flags]
cockpit init --json          # 机器可读输出
cockpit init --dry-run       # 预检 (无副作用)
cockpit init --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit profile`

查看/编辑身份档案 (L4 入口)

**用法**:

```bash
cockpit profile [flags]
cockpit profile --json          # 机器可读输出
cockpit profile --dry-run       # 预检 (无副作用)
cockpit profile --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit quickstart`

🚀 新用户快速上手向导（环境核验 + 上手指引）

**用法**:

```bash
cockpit quickstart [flags]
cockpit quickstart --json          # 机器可读输出
cockpit quickstart --dry-run       # 预检 (无副作用)
cockpit quickstart --help          # 完整参数面
```

  · 所属域: `user`  |  成熟度: stable  |  风险: low  |  别名: `init`

### `cockpit quickstart-check`

快速检查新用户环境核验状态

**用法**:

```bash
cockpit quickstart-check [flags]
cockpit quickstart-check --json          # 机器可读输出
cockpit quickstart-check --dry-run       # 预检 (无副作用)
cockpit quickstart-check --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 📄 专项工具 (Domain)

### `cockpit cartridge`

👁️ 长尾领域治理卡带工坊 (ADR-0198/0203)

**用法**:

```bash
cockpit cartridge [flags]
cockpit cartridge --json          # 机器可读输出
cockpit cartridge --dry-run       # 预检 (无副作用)
cockpit cartridge --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit challenge`

⚡️ 影子红蓝对抗审查与合规自动打补丁 (ADR-0196)

**用法**:

```bash
cockpit challenge [flags]
cockpit challenge --json          # 机器可读输出
cockpit challenge --dry-run       # 预检 (无副作用)
cockpit challenge --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit code`

代码审查与质量管理

**用法**:

```bash
cockpit code [flags]
cockpit code --json          # 机器可读输出
cockpit code --dry-run       # 预检 (无副作用)
cockpit code --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit compute`

算力与计算任务管理

**用法**:

```bash
cockpit compute [flags]
cockpit compute --json          # 机器可读输出
cockpit compute --dry-run       # 预检 (无副作用)
cockpit compute --help          # 完整参数面
```

  · 所属域: `⚡️ 算力与推理 (Compute Fabric, Models, VRAM, Mesh)`  |  成熟度: stable  |  风险: low

### `cockpit decide`

📬 决策收件箱 (列出/添加/批准/拒绝)

**用法**:

```bash
cockpit decide [flags]
cockpit decide --json          # 机器可读输出
cockpit decide --dry-run       # 预检 (无副作用)
cockpit decide --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit family-hub`

家庭数字枢纽入口 (status / api / mcp)

**用法**:

```bash
cockpit family-hub [flags]
cockpit family-hub --json          # 机器可读输出
cockpit family-hub --dry-run       # 预检 (无副作用)
cockpit family-hub --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low

### `cockpit finance`

💰 个人财务门户引导 (场景 / 原则 / 入口)

**用法**:

```bash
cockpit finance [flags]
cockpit finance --json          # 机器可读输出
cockpit finance --dry-run       # 预检 (无副作用)
cockpit finance --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit gongwen`

📄 公文写作门户引导 (文种 / 规范 / 入口)

**用法**:

```bash
cockpit gongwen [flags]
cockpit gongwen --json          # 机器可读输出
cockpit gongwen --dry-run       # 预检 (无副作用)
cockpit gongwen --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low

### `cockpit im-triage`

IM 消息分诊

**用法**:

```bash
cockpit im-triage [flags]
cockpit im-triage --json          # 机器可读输出
cockpit im-triage --dry-run       # 预检 (无副作用)
cockpit im-triage --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit intent`

🧠 自然语言意图解构与工程规格编译器 (ADR-0195)

**用法**:

```bash
cockpit intent [flags]
cockpit intent --json          # 机器可读输出
cockpit intent --dry-run       # 预检 (无副作用)
cockpit intent --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit omo`

OMO 健康自管系统

**用法**:

```bash
cockpit omo [flags]
cockpit omo --json          # 机器可读输出
cockpit omo --dry-run       # 预检 (无副作用)
cockpit omo --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit render`

渲染输出

**用法**:

```bash
cockpit render [flags]
cockpit render --json          # 机器可读输出
cockpit render --dry-run       # 预检 (无副作用)
cockpit render --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 📋 项目 (Project)

### `cockpit agent`

Agent 工作流编排（agent-workflow 别名）

**用法**:

```bash
cockpit agent [flags]
cockpit agent --json          # 机器可读输出
cockpit agent --dry-run       # 预检 (无副作用)
cockpit agent --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low

### `cockpit agent-workflow`

Agent 工作流编排

**用法**:

```bash
cockpit agent-workflow [flags]
cockpit agent-workflow --json          # 机器可读输出
cockpit agent-workflow --dry-run       # 预检 (无副作用)
cockpit agent-workflow --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low  |  别名: `agent`

### `cockpit bcos`

BCOS 业务域系统 (evolve/signals/north-star)

**用法**:

```bash
cockpit bcos [flags]
cockpit bcos --json          # 机器可读输出
cockpit bcos --dry-run       # 预检 (无副作用)
cockpit bcos --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low  |  委派目标: `bin/bc-os/*.py`

### `cockpit c2g`

Concept-to-Governance 生命周期转化

**用法**:

```bash
cockpit c2g [flags]
cockpit c2g --json          # 机器可读输出
cockpit c2g --dry-run       # 预检 (无副作用)
cockpit c2g --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit compass`

战略罗盘 (OKR / 目标对齐)

**用法**:

```bash
cockpit compass [flags]
cockpit compass --json          # 机器可读输出
cockpit compass --dry-run       # 预检 (无副作用)
cockpit compass --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit debt`

技术债管理 (list / score / resolve)

**用法**:

```bash
cockpit debt [flags]
cockpit debt --json          # 机器可读输出
cockpit debt --dry-run       # 预检 (无副作用)
cockpit debt --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low

### `cockpit iterate`

迭代管理 (sprint / backlog / roadmap)

**用法**:

```bash
cockpit iterate [flags]
cockpit iterate --json          # 机器可读输出
cockpit iterate --dry-run       # 预检 (无副作用)
cockpit iterate --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low

### `cockpit kems`

知识经济指标体系 (KEMS · KPI 追踪)

**用法**:

```bash
cockpit kems [flags]
cockpit kems --json          # 机器可读输出
cockpit kems --dry-run       # 预检 (无副作用)
cockpit kems --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low

### `cockpit readiness`

Readiness Dashboard (Phase / Gate / 核验)

**用法**:

```bash
cockpit readiness [flags]
cockpit readiness --json          # 机器可读输出
cockpit readiness --dry-run       # 预检 (无副作用)
cockpit readiness --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low

### `cockpit scenario`

统一 scenario 入口 (radar / assistant / health)

**用法**:

```bash
cockpit scenario [flags]
cockpit scenario --json          # 机器可读输出
cockpit scenario --dry-run       # 预检 (无副作用)
cockpit scenario --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low

### `cockpit wave2`

Wave2 项目战略视图

**用法**:

```bash
cockpit wave2 [flags]
cockpit wave2 --json          # 机器可读输出
cockpit wave2 --dry-run       # 预检 (无副作用)
cockpit wave2 --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit workflow`

工作流管理 (run / list / status)

**用法**:

```bash
cockpit workflow [flags]
cockpit workflow --json          # 机器可读输出
cockpit workflow --dry-run       # 预检 (无副作用)
cockpit workflow --help          # 完整参数面
```

  · 所属域: `📋 智能体与交付 (Workflows, Agent Lifecycle, Residents, BCOS)`  |  成熟度: stable  |  风险: low


## 📚 研究 (Research)

### `cockpit brief`

会话简报 (生成摘要)

**用法**:

```bash
cockpit brief [flags]
cockpit brief --json          # 机器可读输出
cockpit brief --dry-run       # 预检 (无副作用)
cockpit brief --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low

### `cockpit daily`

每日研究简报 (生成 + 推送)

**用法**:

```bash
cockpit daily [flags]
cockpit daily --json          # 机器可读输出
cockpit daily --dry-run       # 预检 (无副作用)
cockpit daily --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit discover`

发现可用功能和资源

**用法**:

```bash
cockpit discover [flags]
cockpit discover --json          # 机器可读输出
cockpit discover --dry-run       # 预检 (无副作用)
cockpit discover --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit knowledge`

本地知识库管理 (import / query / stats)

**用法**:

```bash
cockpit knowledge [flags]
cockpit knowledge --json          # 机器可读输出
cockpit knowledge --dry-run       # 预检 (无副作用)
cockpit knowledge --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low

### `cockpit memory`

Memory OS 统一控制面 (status/recall/write/forget → bos://memory/mos/*)

**用法**:

```bash
cockpit memory [flags]
cockpit memory --json          # 机器可读输出
cockpit memory --dry-run       # 预检 (无副作用)
cockpit memory --help          # 完整参数面
```

  · 所属域: `🧠 记忆与认知 (Memory OS, Knowledge Graph, Search, Brain)`  |  成熟度: stable  |  风险: low  |  别名: `mos`

### `cockpit memory-distill`

记忆蒸馏 (隐藏运维面)

**用法**:

```bash
cockpit memory-distill [flags]
cockpit memory-distill --json          # 机器可读输出
cockpit memory-distill --dry-run       # 预检 (无副作用)
cockpit memory-distill --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit research`

深度研究工作台 (ask / publish / list / audit / …)

**用法**:

```bash
cockpit research [flags]
cockpit research --json          # 机器可读输出
cockpit research --dry-run       # 预检 (无副作用)
cockpit research --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit search`

跨源搜索 (数据库 + BOS 知识引擎)

**用法**:

```bash
cockpit search [flags]
cockpit search --json          # 机器可读输出
cockpit search --dry-run       # 预检 (无副作用)
cockpit search --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low

### `cockpit spine`

Spine 主干真值流与署名自进化操作 (ADR-0437)

**用法**:

```bash
cockpit spine [flags]
cockpit spine --json          # 机器可读输出
cockpit spine --dry-run       # 预检 (无副作用)
cockpit spine --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 📡 通讯 (Messaging)

### `cockpit agora`

Agora BOS 网关入口 (委派 agora CLI)

**用法**:

```bash
cockpit agora [flags]
cockpit agora --json          # 机器可读输出
cockpit agora --dry-run       # 预检 (无副作用)
cockpit agora --help          # 完整参数面
```

  · 所属域: `bus`  |  成熟度: stable  |  风险: low

### `cockpit bus`

Omni-Bus 三平面入口 (status / topics / publish)

**用法**:

```bash
cockpit bus [flags]
cockpit bus --json          # 机器可读输出
cockpit bus --dry-run       # 预检 (无副作用)
cockpit bus --help          # 完整参数面
```

  · 所属域: `🌐 总线与通信 (Omni-Bus, Agora, BOS Services, Events)`  |  成熟度: stable  |  风险: low

### `cockpit events`

实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard)

**用法**:

```bash
cockpit events [flags]
cockpit events --json          # 机器可读输出
cockpit events --dry-run       # 预检 (无副作用)
cockpit events --help          # 完整参数面
```

  · 所属域: `bus`  |  成熟度: stable  |  风险: low

### `cockpit events-watch`

监听 BOS Inbox 紧急待办与提醒快照

**用法**:

```bash
cockpit events-watch [flags]
cockpit events-watch --json          # 机器可读输出
cockpit events-watch --dry-run       # 预检 (无副作用)
cockpit events-watch --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit ssb`

[DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用，请使用 cockpit 替代

**用法**:

```bash
cockpit ssb [flags]
cockpit ssb --json          # 机器可读输出
cockpit ssb --dry-run       # 预检 (无副作用)
cockpit ssb --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 📦 数据 (Data)

### `cockpit contracts`

契约验证 (validate / list / export)

**用法**:

```bash
cockpit contracts [flags]
cockpit contracts --json          # 机器可读输出
cockpit contracts --dry-run       # 预检 (无副作用)
cockpit contracts --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low

### `cockpit data`

数据目录索引 / 类型注册 / TTL 清理

**用法**:

```bash
cockpit data [flags]
cockpit data --json          # 机器可读输出
cockpit data --dry-run       # 预检 (无副作用)
cockpit data --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit import`

导入外部内容 (Markdown / URL / 文件)

**用法**:

```bash
cockpit import [flags]
cockpit import --json          # 机器可读输出
cockpit import --dry-run       # 预检 (无副作用)
cockpit import --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 🔌 总线接入 (ECCP)

### `cockpit channels`

External channels inventory (ECCP)

**用法**:

```bash
cockpit channels [flags]
cockpit channels --json          # 机器可读输出
cockpit channels --dry-run       # 预检 (无副作用)
cockpit channels --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 🖥️ 基础设施 (Infra)

### `cockpit chain`

多命令联动链路编排 (list/show/run/validate/init, YAML 声明式)

**用法**:

```bash
cockpit chain [flags]
cockpit chain --json          # 机器可读输出
cockpit chain --dry-run       # 预检 (无副作用)
cockpit chain --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit dashboard`

打开 Web Dashboard

**用法**:

```bash
cockpit dashboard [flags]
cockpit dashboard --json          # 机器可读输出
cockpit dashboard --dry-run       # 预检 (无副作用)
cockpit dashboard --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low

### `cockpit fabric`

🧑‍💻 主权混合算力与 KV 缓存快照 (ADR-0197)

**用法**:

```bash
cockpit fabric [flags]
cockpit fabric --json          # 机器可读输出
cockpit fabric --dry-run       # 预检 (无副作用)
cockpit fabric --help          # 完整参数面
```

  · 所属域: `compute`  |  成熟度: stable  |  风险: low

### `cockpit fabric-mesh`

算力网格 fabric 检视 (隐藏运维面)

**用法**:

```bash
cockpit fabric-mesh [flags]
cockpit fabric-mesh --json          # 机器可读输出
cockpit fabric-mesh --dry-run       # 预检 (无副作用)
cockpit fabric-mesh --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit mesh`

omlx 算力网格路由入口 (nodes / route / serve)

**用法**:

```bash
cockpit mesh [flags]
cockpit mesh --json          # 机器可读输出
cockpit mesh --dry-run       # 预检 (无副作用)
cockpit mesh --help          # 完整参数面
```

  · 所属域: `compute`  |  成熟度: stable  |  风险: low

### `cockpit model-driven`

[DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行

**用法**:

```bash
cockpit model-driven [flags]
cockpit model-driven --json          # 机器可读输出
cockpit model-driven --dry-run       # 预检 (无副作用)
cockpit model-driven --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit mof`

MOF 元模型操作 (委派 mof CLI)

**用法**:

```bash
cockpit mof [flags]
cockpit mof --json          # 机器可读输出
cockpit mof --dry-run       # 预检 (无副作用)
cockpit mof --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit observe`

可观测性栈（Langfuse）入口 (up / down / logs)

**用法**:

```bash
cockpit observe [flags]
cockpit observe --json          # 机器可读输出
cockpit observe --dry-run       # 预检 (无副作用)
cockpit observe --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit ops`

🔧 Service Gateway — 统一运维控制面

**用法**:

```bash
cockpit ops [flags]
cockpit ops --json          # 机器可读输出
cockpit ops --dry-run       # 预检 (无副作用)
cockpit ops --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit telemetry`

命令全生命周期可观测性与 Prometheus 指标导出

**用法**:

```bash
cockpit telemetry [flags]
cockpit telemetry --json          # 机器可读输出
cockpit telemetry --dry-run       # 预检 (无副作用)
cockpit telemetry --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low

### `cockpit watchdog`

🐕 自治守护犬与自愈探针 (Agora Bus / Resident 监视器)

**用法**:

```bash
cockpit watchdog [flags]
cockpit watchdog --json          # 机器可读输出
cockpit watchdog --dry-run       # 预检 (无副作用)
cockpit watchdog --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low


## 🛠️ 系统 (System)

### `cockpit agent-runtime`

Agent 运行时生命周期管理

**用法**:

```bash
cockpit agent-runtime [flags]
cockpit agent-runtime --json          # 机器可读输出
cockpit agent-runtime --dry-run       # 预检 (无副作用)
cockpit agent-runtime --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit audit`

🔍 6 维度全方位审计

**用法**:

```bash
cockpit audit [flags]
cockpit audit --json          # 机器可读输出
cockpit audit --dry-run       # 预检 (无副作用)
cockpit audit --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low

### `cockpit capabilities`

统一能力发现入口 — 搜索/推荐/全量列出 (CLI+BOS+Scene+Journey)

**用法**:

```bash
cockpit capabilities [flags]
cockpit capabilities --json          # 机器可读输出
cockpit capabilities --dry-run       # 预检 (无副作用)
cockpit capabilities --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit gac`

GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift)

**用法**:

```bash
cockpit gac [flags]
cockpit gac --json          # 机器可读输出
cockpit gac --dry-run       # 预检 (无副作用)
cockpit gac --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low

### `cockpit health`

一键系统健康检查 (7 维度)

**用法**:

```bash
cockpit health [flags]
cockpit health --json          # 机器可读输出
cockpit health --dry-run       # 预检 (无副作用)
cockpit health --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low

### `cockpit journey`

Journey State Graph 状态表达校验器

**用法**:

```bash
cockpit journey [flags]
cockpit journey --json          # 机器可读输出
cockpit journey --dry-run       # 预检 (无副作用)
cockpit journey --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low

### `cockpit monitor`

实时监控 (进程 / 资源 / 指标)

**用法**:

```bash
cockpit monitor [flags]
cockpit monitor --json          # 机器可读输出
cockpit monitor --dry-run       # 预检 (无副作用)
cockpit monitor --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit panorama`

7 维全景终极可观测仪表盘 (执行/服务/内容/知识/数据/异常/债务)

**用法**:

```bash
cockpit panorama [flags]
cockpit panorama --json          # 机器可读输出
cockpit panorama --dry-run       # 预检 (无副作用)
cockpit panorama --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit product-health`

产品健康度检测

**用法**:

```bash
cockpit product-health [flags]
cockpit product-health --json          # 机器可读输出
cockpit product-health --dry-run       # 预检 (无副作用)
cockpit product-health --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit project`

16 项目全景 4D 体检与诊断

**用法**:

```bash
cockpit project [flags]
cockpit project --json          # 机器可读输出
cockpit project --dry-run       # 预检 (无副作用)
cockpit project --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit proxy-env`

输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE)

**用法**:

```bash
cockpit proxy-env [flags]
cockpit proxy-env --json          # 机器可读输出
cockpit proxy-env --dry-run       # 预检 (无副作用)
cockpit proxy-env --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit runtime`

运行时环境管理

**用法**:

```bash
cockpit runtime [flags]
cockpit runtime --json          # 机器可读输出
cockpit runtime --dry-run       # 预检 (无副作用)
cockpit runtime --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low

### `cockpit status`

系统健康仪表盘 (Phase / CARDS / 研究工作台)

**用法**:

```bash
cockpit status [flags]
cockpit status --json          # 机器可读输出
cockpit status --dry-run       # 预检 (无副作用)
cockpit status --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low

### `cockpit tui`

极客终端交互控制台 (Textual 全屏 TUI · Vim 键盘流)

**用法**:

```bash
cockpit tui [flags]
cockpit tui --json          # 机器可读输出
cockpit tui --dry-run       # 预检 (无副作用)
cockpit tui --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit version`

版本信息

**用法**:

```bash
cockpit version [flags]
cockpit version --json          # 机器可读输出
cockpit version --dry-run       # 预检 (无副作用)
cockpit version --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 🤖 Agent 协作

### `cockpit agent-onboard`

新 Agent 入职 checklist + 环境初始化

**用法**:

```bash
cockpit agent-onboard [flags]
cockpit agent-onboard --json          # 机器可读输出
cockpit agent-onboard --dry-run       # 预检 (无副作用)
cockpit agent-onboard --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit cell`

🤖 AGE-v2 动态 Agent Cell (规划/执行/验证/治理)

**用法**:

```bash
cockpit cell [flags]
cockpit cell --json          # 机器可读输出
cockpit cell --dry-run       # 预检 (无副作用)
cockpit cell --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit resident`

Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...)

**用法**:

```bash
cockpit resident [flags]
cockpit resident --json          # 机器可读输出
cockpit resident --dry-run       # 预检 (无副作用)
cockpit resident --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low  |  委派目标: `omo resident`

### `cockpit swarm`

多 agent 实时活动监控 (runs/locks/worktree/冲突)

**用法**:

```bash
cockpit swarm [flags]
cockpit swarm --json          # 机器可读输出
cockpit swarm --dry-run       # 预检 (无副作用)
cockpit swarm --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## 🧠 知识引擎 (BOS)

### `cockpit ask`

快速大模型对话问答 (AetherForge)

**用法**:

```bash
cockpit ask [flags]
cockpit ask --json          # 机器可读输出
cockpit ask --dry-run       # 预检 (无副作用)
cockpit ask --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit bos`

BOS URI 查询与管理 (list / resolve / read / inbox / …)

**用法**:

```bash
cockpit bos [flags]
cockpit bos --json          # 机器可读输出
cockpit bos --dry-run       # 预检 (无副作用)
cockpit bos --help          # 完整参数面
```

  · 所属域: `bus`  |  成熟度: stable  |  风险: low

### `cockpit bos-capability`

BOS capability 域 / toolbox 外部能力 (list / invoke)

**用法**:

```bash
cockpit bos-capability [flags]
cockpit bos-capability --json          # 机器可读输出
cockpit bos-capability --dry-run       # 预检 (无副作用)
cockpit bos-capability --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit bos-inbox`

BOS Inbox 多源私有知识神经网查询与操作

**用法**:

```bash
cockpit bos-inbox [flags]
cockpit bos-inbox --json          # 机器可读输出
cockpit bos-inbox --dry-run       # 预检 (无副作用)
cockpit bos-inbox --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit brain`

个人数字大脑 (ask / remember / history / context)

**用法**:

```bash
cockpit brain [flags]
cockpit brain --json          # 机器可读输出
cockpit brain --dry-run       # 预检 (无副作用)
cockpit brain --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low

### `cockpit domains`

列出 L4 所有域及其状态

**用法**:

```bash
cockpit domains [flags]
cockpit domains --json          # 机器可读输出
cockpit domains --dry-run       # 预检 (无副作用)
cockpit domains --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit gbrain`

Postgres-native 知识库 (search / import / stats)

**用法**:

```bash
cockpit gbrain [flags]
cockpit gbrain --json          # 机器可读输出
cockpit gbrain --dry-run       # 预检 (无副作用)
cockpit gbrain --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low

### `cockpit kairon`

kairon 知识引擎 monorepo 聚合入口

**用法**:

```bash
cockpit kairon [flags]
cockpit kairon --json          # 机器可读输出
cockpit kairon --dry-run       # 预检 (无副作用)
cockpit kairon --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low

### `cockpit skill`

运行 L4 定时技能

**用法**:

```bash
cockpit skill [flags]
cockpit skill --json          # 机器可读输出
cockpit skill --dry-run       # 预检 (无副作用)
cockpit skill --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low

### `cockpit vault`

搜索 L4 Vault 知识库

**用法**:

```bash
cockpit vault [flags]
cockpit vault --json          # 机器可读输出
cockpit vault --dry-run       # 预检 (无副作用)
cockpit vault --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low


## 遗留命令映射

| 命令 | 域 | 目标 |
|------|-----|------|
| `cockpit agent` | workflow | agent |
| `cockpit agent-workflow` | workflow | workflow |
| `cockpit agora` | bus | agora |
| `cockpit audit` | governance | audit |
| `cockpit bcos` | workflow | bcos |
| `cockpit bos` | bus | bos |
| `cockpit brain` | memory | brain |
| `cockpit brief` | scene | brief |
| `cockpit bus` | bus | bus |
| `cockpit capability` | bus | capability |
| `cockpit completion` | user | completion |
| `cockpit contracts` | governance | contracts |
| `cockpit dashboard` | system | dashboard |
| `cockpit debt` | governance | debt |
| `cockpit demo` | user | demo |
| `cockpit docs` | user | docs |
| `cockpit events` | bus | events |
| `cockpit fabric` | compute | fabric |
| `cockpit family-hub` | scene | family-hub |
| `cockpit gac` | governance | gac |
| `cockpit gbrain` | memory | gbrain |
| `cockpit gongwen` | scene | gongwen |
| `cockpit health` | system | health |
| `cockpit help` | user | help |
| `cockpit iterate` | workflow | iterate |
| `cockpit journey` | scene | journey |
| `cockpit kairon` | memory | kairon |
| `cockpit kems` | governance | kems |
| `cockpit knowledge` | memory | knowledge |
| `cockpit memory` | memory | memory |
| `cockpit mesh` | compute | mesh |
| `cockpit policy` | governance | policy |
| `cockpit quickstart` | user | quickstart |
| `cockpit readiness` | system | readiness |
| `cockpit resident` | workflow | resident |
| `cockpit runtime` | system | runtime |
| `cockpit scenario` | scene | scenario |
| `cockpit search` | memory | search |
| `cockpit status` | system | status |
| `cockpit telemetry` | system | telemetry |
| `cockpit triage` | compute | triage |
| `cockpit vault` | memory | vault |
| `cockpit vram` | compute | vram |
| `cockpit warm` | compute | warm |
| `cockpit watchdog` | governance | watchdog |

## 扫描发现的其他命令

| 命令 | 描述 |
|------|------|
| `cockpit ack` | 确认任务完成 |
| `cockpit add` | 手动添加决策项 |
| `cockpit analyze` | 运行全部分析工具 |
| `cockpit api` | 启动 API server |
| `cockpit approve` | 批准决策 |
| `cockpit archive` | 归档研究记录 |
| `cockpit backends` | 列出 BOS 后端 |
| `cockpit backup` | 全量备份研究数据到 JSON 文件 |
| `cockpit backup-restore` | 从备份 JSON 文件恢复研究数据 |
| `cockpit batch` | 批量研究模式: 逐个处理多个 topic，汇总结果 |
| `cockpit cache` | 检查三级分层缓存与 Radix 前缀树状态 (含基准压测) |
| `cockpit client` | 以 REPL 模式连接到 MCP server |
| `cockpit cluster` | 异构三节点智能路由与拓扑诊断 |
| `cockpit compact` | 上下文滑动蒸馏与双区自适应量化压缩模拟 |
| `cockpit compare` | 对比多个研究结果 |
| `cockpit consolidate` | sleep-time 巩固 (默认 dry-run) |
| `cockpit control` | 控制平面：submit / ack / nack |
| `cockpit create` | 创建新研究 |
| `cockpit dflash` | DFlash 2 块扩散投机解码加速与集群基准 |
| `cockpit diff` | 查看待处理署名 Diff 统计 |
| `cockpit digest` | 提炼多个研究结果 |
| `cockpit distill` | 在 Mac mini M4 触发闲时 LoRA 蒸馏 |
| `cockpit dma` | 测试雷雳 5 跨机零拷贝 DMA 通道与换页基准 |
| `cockpit docx` | 渲染为 GB/T 9704-2012 红头公文 DOCX |
| `cockpit dossier` | 查看研究的关系与产物视图 |
| `cockpit down` | 停止观测栈 |
| `cockpit draft` | 从本地主权大模型请求草稿 |
| `cockpit event` | 导出事件封套 (EventEnvelope) |
| `cockpit export` | 导出研究 (markdown/text/json) |
| `cockpit export-research` | 将研究对象导出为 WorkspaceObject JSON |
| `cockpit follow-up` | 查看追问工作台（待追问/已回答统计） |
| `cockpit forget` | 遗忘传播 |
| `cockpit gc` | 清理 data/tmp 过期文件 |
| `cockpit get` | 查 1 个 card |
| `cockpit graph` | 运行语义图谱分析 |
| `cockpit heatmap` | 显示研究活跃度热力图 |
| `cockpit history` | 查看对话历史 |
| `cockpit hud` | 查看次世代主权算力织网全景 HUD 实时状态 |
| `cockpit identity` | 导出身份封套 (IdentityEnvelope) |
| `cockpit impact` | 分析符号的变更影响面 |
| `cockpit inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit index` | 刷新 data/_index 元数据 |
| `cockpit ingress` | 感知源接入 Spine 管线 (T2-03: OCR 扫描件) |
| `cockpit inspect` | 查看算力网格健康度与节点状态 |
| `cockpit invoke` | 通过治理网关调用 exact native BOS capability |
| `cockpit knowledge-ref` | ADR-0315 引用元数据 (无正文) |
| `cockpit list` | 查看研究历史 |
| `cockpit logs` | 查看日志 |
| `cockpit lora` | 查看与测试端侧在线 LoRA 适配层热插拔 |
| `cockpit merge` | 合并多个研究结果为新研究 |
| `cockpit metrics` | 查看 bus metrics 快照 |
| `cockpit mutate` | 通过 agora 统一 BOS URI 写协议修改资源 |
| `cockpit nack` | 否定确认任务 |
| `cockpit nodes` | 列出 KOS 中注册的算力节点 |
| `cockpit onboarding` | 为 AI 构建项目全貌上下文 |
| `cockpit open` | 打开研究全文 |
| `cockpit pack` | 将代码库打包为 LLM 友好格式 |
| `cockpit pending` | 查看未决待办快照预览 |
| `cockpit pipeline` | pipeline 概览 |
| `cockpit pptx` | 渲染为 16:9 高管技术汇报 PPTX |
| `cockpit publish` | 发布研究为正式 Markdown 报告 |
| `cockpit quarantine` | 隔离可疑研究记录 |
| `cockpit read` | 通过 BOS 网关统一读取指定 URI 资源 |
| `cockpit recall` | 意图路由召回（neo4j/temporal 支持 --as-of） |
| `cockpit register` | 注册 BOS 服务 |
| `cockpit reject` | 拒绝决策 |
| `cockpit reload` | 重载 BOS 配置/M1 |
| `cockpit remember` | 手动存入偏好/事实 |
| `cockpit rename` | 重命名研究标题 |
| `cockpit replay` | 查看 Experience Replay 缓冲区状态 |
| `cockpit resolve` | 统一 BOS URI 路由解析与目标元数据提取 |
| `cockpit restore` | 恢复已隔离研究记录 |
| `cockpit route` | 为模型选择最优节点 |
| `cockpit run` | 在隔离沙箱中挂载卡带并执行领域意图 |
| `cockpit scan` | 平面扫描 |
| `cockpit scene` | 🗺️ 业务场景正交领域 (scenario/journey/gongwen/brief/family-hub) |
| `cockpit score` | 评分债务项 |
| `cockpit serve` | stdio JSON-RPC serve mode |
| `cockpit sign` | 提交用户署名 Diff 并入队 Experience Replay |
| `cockpit snapshot` | KV 缓存快照管理与预热 |
| `cockpit speculative-eval` | 本地首选投机推演评估 |
| `cockpit stats` | 索引统计 |
| `cockpit stream` | 跨节点 Chunk-level 流式协同流水线基准 |
| `cockpit submit` | 提交控制任务 |
| `cockpit summary` | 债务摘要 (委派 omo debt) |
| `cockpit svg` | 渲染 ```diagram 代码块为矢量架构图 SVG |
| `cockpit system` | 🖥️ 系统与运维正交领域 (status/health/dashboard/readiness/runtime) |
| `cockpit tag` | 为研究添加/覆盖标签 |
| `cockpit test_export_formats` | 离线自测: 三格式导出 + GB/T 参数断言 |
| `cockpit timeline` | 查看研究的演化时间线 |
| `cockpit topics` | 列出已注册 topic |
| `cockpit tree` | 自适应熵感知树状投机解码与多候选验证基准 |
| `cockpit types` | 查看已注册的数据类型 |
| `cockpit unarchive` | 恢复已归档研究记录 |
| `cockpit up` | 启动观测栈 |
| `cockpit url` | 打印 Langfuse Web URL |
| `cockpit user` | 👤 用户体验与向导正交领域 (quickstart/help/demo/init/profile/completion) |
| `cockpit validate` | 验证 Workspace 契约 |
| `cockpit watch` | 监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher) |
| `cockpit write` | 双轨写入 (+ Neo4j FACT 若配置) |

## 全局 Flags

所有命令共享的全局参数面:

| Flag | 说明 |
|------|------|
| `--help` / `-h` | 命令帮助 |
| `--version` / `-V` | 版本号 |
| `--json` | 机器可读 JSON 输出 |
| `--dry-run` | 预检模式 (不执行副作用) |
| `--quiet` / `-q` | 静默模式 |
| `--verbose` / `-v` | 详细输出 |
| `--output` / `-o` | 输出文件路径 |
| `--trace-id` | 链路追踪 ID (跨命令 trace 贯穿) |

## Shell 自动补全

```bash
source <(cockpit completion bash)   # Bash
source <(cockpit completion zsh)    # Zsh
cockpit completion fish | source    # Fish
```

输错命令时会给出 Levenshtein 最近邻建议 (`Did you mean ...`)。

## MCP 工具映射

| CLI 命令 | MCP 服务器 | 工具数 |
|----------|-----------|--------|
| `cockpit omo` | `omo` | 22 |
| `cockpit kairon` | `kos/iris/sophia/kronos/minerva/codeanalyze/forge/ontoderive` | 123 |
| `cockpit gbrain` | `gbrain` | 75 |
| `cockpit model-driven` | `model-driven` | 28 |
| `cockpit agora` | `agora` | 104 |
| `cockpit family-hub` | `family-hub` | 6 |
| `cockpit mesh` | `aetherforge` | 15 |
| `cockpit compute` | `aetherforge` | 15 |

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成 (T8-16 全量模式)*