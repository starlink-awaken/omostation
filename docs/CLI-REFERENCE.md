---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-09
---
# Cockpit CLI Reference Manual

> **Version**: v0.4.0 | **Standard**: Tier-1 Open Source CLI Specification (gh / kubectl compatible)
> **Generated**: Automatic via `cockpit docs export`

---

## Table of Contents
1. [Global Flags & Universal Contract](#1-global-flags--universal-contract)
2. [Standard Exit Codes](#2-standard-exit-codes)
3. [The 8 Orthogonal Domains (Dual-Track Architecture)](#3-the-8-orthogonal-domains-dual-track-architecture)
4. [Command Catalog](#4-command-catalog)
5. [Observability & Prometheus Telemetry](#5-observability--prometheus-telemetry)
6. [Shell Auto-completion](#6-shell-auto-completion)

---

## 1. Global Flags & Universal Contract
Cockpit implements universal flags across all subcommands. Output purity is strictly guaranteed: `--json` guarantees 100% pure JSON without ANSI color escape codes.

| Flag | Alias | Description | Output Mode |
| :--- | :--- | :--- | :--- |
| `--help` | `-h` | Display contextual help and subcommands | Text |
| `--version` | `-V` | Print version string with <40ms fast-path | Text |
| `--json` | - | Output pure structured JSON (disables Rich ANSI) | JSON |
| `--dry-run` | - | Preflight check without side effects or disk writes | JSON / Text |
| `--quiet` | `-q` | Suppress non-essential informational banners | Quiet |
| `--verbose` | `-v` | Output execution trace and diagnostic details | Verbose |
| `--output` | `-o` | Select format: `text`, `json`, `tui`, `markdown` | Formatted |
| `--trace-id` | - | Explicit distributed trace ID for OpenTelemetry/Langfuse | - |

---

## 2. Standard Exit Codes
All cockpit commands return POSIX-compliant exit codes according to the `ExitCode` contract:

| Code | Name | Semantic Description |
| :---: | :--- | :--- |
| `0` | `SUCCESS` | Normal execution completed successfully |
| `1` | `GENERAL_FAILURE` | Assertion failed or general business logic error |
| `2` | `USAGE_ERROR` | Command-line argument error, invalid choice, typo |
| `3` | `PERMISSION_DENIED` | Authentication failure or RBAC domain restriction |
| `4` | `RESOURCE_NOT_FOUND` | Target resource, task, or file not found |
| `5` | `UPSTREAM_ERROR` | Downstream service timeout, circuit breaker open, or unreachable |

---

## 3. The 8 Orthogonal Domains (Dual-Track Architecture)
Commands are organized into 8 orthogonal top-level domains. Both hierarchical calls (`cockpit <domain> <subcommand>`) and legacy flat calls (`cockpit <subcommand>`) are 100% equivalent and supported.

| Domain | Icon | Description | Core Subcommands | Example |
| :--- | :---: | :--- | :--- | :--- |
| `governance` | 🏛️ | 🏛️ 架构与治理 (Governance, Contracts, GAC, Audits) | `audit`, `contracts`, `debt`, `gac`, `kems`, `policy` (+1 more) | `cockpit governance audit` |
| `workflow` | 📋 | 📋 智能体与交付 (Workflows, Agent Lifecycle, Residents, BCOS) | `agent`, `agent-workflow`, `bcos`, `iterate`, `resident` | `cockpit workflow agent` |
| `memory` | 🧠 | 🧠 记忆与认知 (Memory OS, Knowledge Graph, Search, Brain) | `brain`, `gbrain`, `kairon`, `knowledge`, `memory`, `search` (+1 more) | `cockpit memory brain` |
| `compute` | ⚡️ | ⚡️ 算力与推理 (Compute Fabric, Models, VRAM, Mesh) | `fabric`, `mesh`, `triage`, `vram`, `warm` | `cockpit compute fabric` |
| `bus` | 🌐 | 🌐 总线与通信 (Omni-Bus, Agora, BOS Services, Events) | `agora`, `bos`, `bus`, `capability`, `events` | `cockpit bus agora` |
| `scene` | 🗺️ | 🗺️ 业务场景 (Scenario Cards, Journeys, Gongwen, Brief) | `brief`, `family-hub`, `gongwen`, `journey`, `scenario`, `spine` | `cockpit scene brief` |
| `system` | 🖥️ | 🖥️ 系统与运维 (System Health, Dashboard, Runtime Sandbox) | `dashboard`, `health`, `readiness`, `runtime`, `status`, `telemetry` | `cockpit system dashboard` |
| `user` | 👤 | 👤 体验与向导 (Quickstart, Help, Onboarding, TUI) | `completion`, `demo`, `docs`, `help`, `quickstart` | `cockpit user completion` |

---

## 4. Command Catalog
Complete inventory of supported subcommands grouped by category:

### 📚 研究 (Research)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `brief` | 会话简报 (生成摘要) | `cockpit brief` |
| `daily` | 每日研究简报 (生成 + 推送) | `cockpit daily` |
| `discover` | 发现可用功能和资源 | `cockpit discover` |
| `knowledge` | 本地知识库管理 (import / query / stats) | `cockpit knowledge` |
| `memory` | Memory OS 统一控制面 (status/recall/write/forget → bos://memory/mos/*) | `cockpit memory` |
| `memory-distill` | 🧠 [DEPRECATED] 记忆蒸馏 ADR-0200 → KOS pipeline (gbrain + eidos) | `cockpit memory-distill` |
| `research` | 深度研究工作台 (ask / publish / list / audit / …) | `cockpit research` |
| `search` | 跨源搜索 (数据库 + BOS 知识引擎) | `cockpit search` |

### 🧠 知识引擎 (BOS)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `ask` | 快速大模型对话问答 (AetherForge) | `cockpit ask` |
| `bos` | BOS URI 查询与管理 (list / resolve / read / inbox / …) | `cockpit bos` |
| `bos-capability` | BOS capability 域 / toolbox 外部能力 (list / invoke) | `cockpit bos-capability` |
| `bos-inbox` | BOS Inbox 多源私有知识神经网查询与操作 | `cockpit bos-inbox` |
| `brain` | 个人数字大脑 (ask / remember / history / context) | `cockpit brain` |
| `domains` | 列出 L4 所有域及其状态 | `cockpit domains` |
| `gbrain` | Postgres-native 知识库 (search / import / stats) | `cockpit gbrain` |
| `kairon` | kairon 知识引擎 monorepo 聚合入口 | `cockpit kairon` |
| `skill` | 运行 L4 定时技能 | `cockpit skill` |
| `vault` | 搜索 L4 Vault 知识库 | `cockpit vault` |

### 📋 项目 (Project)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `agent` | Agent 工作流编排（agent-workflow 别名） | `cockpit agent` |
| `agent-workflow` | Agent 工作流编排 | `cockpit agent-workflow` |
| `bcos` | BCOS 业务域系统 (evolve/signals/north-star) | `cockpit bcos` |
| `c2g` | Concept-to-Governance 生命周期转化 | `cockpit c2g` |
| `compass` | 战略罗盘 (OKR / 目标对齐) | `cockpit compass` |
| `debt` | 技术债管理 (list / score / resolve) | `cockpit debt` |
| `iterate` | 迭代管理 (sprint / backlog / roadmap) | `cockpit iterate` |
| `kems` | 知识经济指标体系 (KEMS · KPI 追踪) | `cockpit kems` |
| `readiness` | Readiness Dashboard (Phase / Gate / 核验) | `cockpit readiness` |
| `scenario` | 统一 scenario 入口 (radar / assistant / health) | `cockpit scenario` |
| `wave2` | Wave2 项目战略视图 | `cockpit wave2` |
| `workflow` | 工作流管理 (run / list / status) | `cockpit workflow` |

### 🤖 Agent 协作

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `agent-onboard` | 新 Agent 入职 checklist + 环境初始化 | `cockpit agent-onboard` |
| `cell` | 🤖 AGE-v2 动态 Agent Cell (规划/执行/验证/治理) | `cockpit cell` |
| `resident` | Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...) | `cockpit resident` |
| `swarm` | 多 agent 实时活动监控 (runs/locks/worktree/冲突) | `cockpit swarm` |

### 🛡️ 治理工具 (Governance Tools)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `adr-coverage` | ADR 覆盖率校验: 编号连续性、frontmatter 完整性、INDEX.md 引用与重复编号检测 | `cockpit adr-coverage` |
| `adr-drift-apply` | 应用 ADR 漂移修复: 对 SUBDIR_MISSING 类型 touch 占位文件 (支持 --dry-run) | `cockpit adr-drift-apply` |
| `adr-drift-auto-fix` | ADR 漂移自动分类与修复建议 (TEMPLATE/ASPIRATIONAL/SUBDIR_MISSING/REAL_BUG/TYPO) | `cockpit adr-drift-auto-fix` |
| `adr-drift-check` | ADR 漂移检测: ADR 引用的 .omo 路径 / bin 工具 / ADR-XXXX 编号是否存在 | `cockpit adr-drift-check` |
| `adr-drift-classify` | ADR 漂移归类: 区分历史预期 (P28-P49 archived) 与新增待修 issue, 可出 markdown 报告 | `cockpit adr-drift-classify` |
| `adr-frontmatter-backfill` | 补齐历史 ADR 的 id: ADR-NNNN frontmatter (幂等; --strict 可作 CI 门) | `cockpit adr-frontmatter-backfill` |
| `adr-next-id` | 建议 (可用 --claim 原子认领) 下一个空闲 ADR 编号, flock 防并发双分配 | `cockpit adr-next-id` |
| `adr-trend-insight` | ADR 趋势洞察: 数量增长曲线、引用健康度趋势、top modified 与 frontmatter 完整度 | `cockpit adr-trend-insight` |

### 🏛️ 治理 (Governance)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `audit-ledger` | 📒 [DEPRECATED] 治理审计账本 ADR-0201 → 查询 .omo/_knowledge/decisions/ + cockpit command-audit | `cockpit audit-ledger` |
| `bdsk` | B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演) | `cockpit bdsk` |
| `cards` | CARDS 卡片状态管理 (list / get / search / serve) | `cockpit cards` |
| `command-audit` | 15 维命令评分卡管理 (init/validate/report/lint) | `cockpit command-audit` |
| `context` | 显示系统上下文 (Phase / CARDS / 约束 / 引导) | `cockpit context` |
| `controller-shadow` | 读取 Runtime 旧控制器影子迁移回执 | `cockpit controller-shadow` |
| `dlp-guard` | 外发前防泄密扫描 (敏感识别+挂起+脱敏) | `cockpit dlp-guard` |
| `domain-status` | 显示 Documents 域项目绑定与引导状态 | `cockpit domain-status` |
| `facts-audit` | 审计 Documents 文档域 facts 文件 | `cockpit facts-audit` |
| `facts-validation` | 读取 Runtime Facts 审计回执 | `cockpit facts-validation` |
| `governance` | 架构治理 (委派 arcnode-*) | `cockpit governance` |
| `harness` | Harness 全生命周期合规 (trace/verify/gac/compliance/…) | `cockpit harness` |
| `mcp` | 启动 MCP server 或列出工具 | `cockpit mcp` |
| `model-freshness` | 读取 Runtime 模型新鲜度回执 | `cockpit model-freshness` |
| `policy` | ⚖️ 领域监管合规与 Policy-as-Code 红线审查 (E-POL-*) | `cockpit policy` |
| `sanyi-status` | 读取 Runtime 三医状态一致性回执 | `cockpit sanyi-status` |

### 🧹 代码质量 (Code Quality)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `sweep-nested-with` | 合并可证明安全的嵌套 with 语句（SIM117 结构改写，AST 解析兜底） | `cockpit sweep-nested-with` |
| `sweep-pyright` | 从 pyright JSON 诊断报告施加显式抑制（支持 --package 过滤与 --dry-run） | `cockpit sweep-pyright` |
| `sweep-ruff` | 对指定路径执行有界 ruff 安全修复循环（默认 3 轮收敛） | `cockpit sweep-ruff` |
| `sweep-scan` | 全仓或 diff 模式 pyright 扫描并归档抑制指标报告到 .omo/_knowledge/sweeps/ | `cockpit sweep-scan` |

### 🖥️ 基础设施 (Infra)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `chain` | 多命令联动链路编排 (list/show/run/validate/init, YAML 声明式) | `cockpit chain` |
| `dashboard` | 打开 Web Dashboard | `cockpit dashboard` |
| `fabric` | 🧑‍💻 主权混合算力与 KV 缓存快照 (ADR-0197) | `cockpit fabric` |
| `fabric-mesh` | 🕸️ [DEPRECATED] 算力网格检视 ADR-0202 → omlxc-compute-fabric skill | `cockpit fabric-mesh` |
| `mesh` | omlx 算力网格路由入口 (nodes / route / serve) | `cockpit mesh` |
| `model-driven` | [DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行 | `cockpit model-driven` |
| `mof` | MOF 元模型操作 (委派 mof CLI) | `cockpit mof` |
| `observe` | 可观测性栈（Langfuse）入口 (up / down / logs) | `cockpit observe` |
| `ops` | 🔧 Service Gateway — 统一运维控制面 | `cockpit ops` |
| `telemetry` | 命令全生命周期可观测性与 Prometheus 指标导出 | `cockpit telemetry` |
| `watchdog` | 🐕 [DEPRECATED] 自治守护犬已退役 → Mesh-bound capability admission (Cockpit PR #78) | `cockpit watchdog` |

### 📡 通讯 (Messaging)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `agora` | Agora BOS 网关入口 (委派 agora CLI) | `cockpit agora` |
| `bus` | Omni-Bus 三平面入口 (status / topics / publish) | `cockpit bus` |
| `events` | 实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard) | `cockpit events` |
| `events-watch` | 监听 BOS Inbox 紧急待办与提醒快照 | `cockpit events-watch` |
| `ssb` | [DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用，请使用 cockpit 替代 | `cockpit ssb` |

### 🔌 项目 CLI (Project CLIs)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `ecos-partition-lint` | ecos 分区导入边界 lint (ADR-0181) — 检查包内导入是否越过分区映射 | `cockpit ecos-partition-lint` |
| `l4-kernel` | L4 自我层管理面 — DomainManifest 校验、知识域登记、只读门禁、内容审计 | `cockpit l4-kernel` |
| `metaos` | MetaOS CLI — 编排/治理层: 决策门控、免疫监控、路由、数字资产引擎 | `cockpit metaos` |
| `metaos-agent` | MetaOS provider agent 会话 — prepare/context/approve/reject 等门控会话管理 | `cockpit metaos-agent` |
| `mof-contract-agent` | BOS 契约分析与修复 — analyze (URI 影响) / diagnose (错误日志) | `cockpit mof-contract-agent` |
| `mof-contract-lint` | BOS 服务契约校验 — 错误解释 (--explain) 与 URI 变更影响分析 (--impact) | `cockpit mof-contract-lint` |
| `omlxc` | omlx 本地算力枢纽 CLI — daemon 状态、模型别名解析 (omlxcd daemon 不在此入口) | `cockpit omlxc` |

### 🧰 工具集 (Utilities)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `change-lane-check` | 检查 staged/unstaged 变更的车道 (lane) 合规性 | `cockpit change-lane-check` |
| `cockpit-readiness` | P65 cockpit readiness 汇总 (委派 governance-dashboard --readiness-summary) | `cockpit cockpit-readiness` |
| `commit-assist` | LLM 辅助生成 Conventional Commits 提交信息 (aetherforge → ollama → heuristic) | `cockpit commit-assist` |
| `compass-radar` | 调 c2g 真审计并写 health SSOT | `cockpit compass-radar` |
| `delegation-alias-check` | opencode ↔ omlx 网关模型别名双向交叉检查 | `cockpit delegation-alias-check` |
| `delegation-preflight` | 会话启动前检查 subagent 委托基础设施 | `cockpit delegation-preflight` |
| `health-ssot` | 校验 health_score SSOT 引用与时效 | `cockpit health-ssot` |
| `layer-dependency-check` | 分层依赖检查器 (layer contract 校验) | `cockpit layer-dependency-check` |
| `scheduler-compile` | 编译/校验定时任务 (crontab 生成) | `cockpit scheduler-compile` |
| `ssot-watcher` | SSOT 变更追踪与自动化 (status/log/preview/sync) | `cockpit ssot-watcher` |
| `submodule-gitlink-check` | 检查 submodule gitlink 指针与远端一致性 | `cockpit submodule-gitlink-check` |
| `tool-registry-audit` | bin/scripts 工具注册表审计 (快照对比 / emit / strict) | `cockpit tool-registry-audit` |

### 📦 数据 (Data)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `contracts` | 契约验证 (validate / list / export) | `cockpit contracts` |
| `data` | 数据目录索引 / 类型注册 / TTL 清理 | `cockpit data` |
| `import` | 导入外部内容 (Markdown / URL / 文件) | `cockpit import` |

### 🛠️ 系统 (System)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `agent-runtime` | Agent 运行时生命周期管理 | `cockpit agent-runtime` |
| `audit` | 🔍 6 维度全方位审计 | `cockpit audit` |
| `capabilities` | 统一能力发现入口 — 搜索/推荐/全量列出 (CLI+BOS+Scene+Journey) | `cockpit capabilities` |
| `gac` | GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift) | `cockpit gac` |
| `health` | 一键系统健康检查 (7 维度) | `cockpit health` |
| `journey` | Journey State Graph 状态表达校验器 | `cockpit journey` |
| `monitor` | 实时监控 (进程 / 资源 / 指标) | `cockpit monitor` |
| `panorama` | 7 维全景终极可观测仪表盘 (执行/服务/内容/知识/数据/异常/债务) | `cockpit panorama` |
| `product-health` | 产品健康度检测 | `cockpit product-health` |
| `project` | 16 项目全景 4D 体检与诊断 | `cockpit project` |
| `proxy-env` | 输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE) | `cockpit proxy-env` |
| `runtime` | 运行时环境管理 | `cockpit runtime` |
| `status` | 系统健康仪表盘 (Phase / CARDS / 研究工作台) | `cockpit status` |
| `tui` | 极客终端交互控制台 (Textual 全屏 TUI · Vim 键盘流) | `cockpit tui` |
| `version` | 版本信息 | `cockpit version` |

### 👤 用户 (User)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `completion` | 生成 Shell 自动补全脚本 (bash/zsh/fish) | `cockpit completion` |
| `demo` | 快速演示 | `cockpit demo` |
| `docs` | CLI 参考手册生成与导出 (docs/CLI-REFERENCE.md) | `cockpit docs` |
| `help` | 查看产品地图与快速入门 | `cockpit help` |
| `init` | 🚀 初始化向导（同 quickstart） | `cockpit init` |
| `profile` | 查看/编辑身份档案 (L4 入口) | `cockpit profile` |
| `quickstart` | 🚀 新用户快速上手向导（环境核验 + 上手指引） | `cockpit quickstart` |
| `quickstart-check` | 快速检查新用户环境核验状态 | `cockpit quickstart-check` |

### 📄 专项工具 (Domain)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `cartridge` | 👁️ 长尾领域治理卡带工坊 (ADR-0198/0203) | `cockpit cartridge` |
| `challenge` | ⚡️ 影子红蓝对抗审查与合规自动打补丁 (ADR-0196) | `cockpit challenge` |
| `code` | 代码审查与质量管理 | `cockpit code` |
| `compute` | 算力与计算任务管理 | `cockpit compute` |
| `decide` | 📬 决策收件箱 (列出/添加/批准/拒绝) | `cockpit decide` |
| `family-hub` | 家庭数字枢纽入口 (status / api / mcp) | `cockpit family-hub` |
| `finance` | 💰 个人财务门户引导 (场景 / 原则 / 入口) | `cockpit finance` |
| `gongwen` | 📄 公文写作门户引导 (文种 / 规范 / 入口) | `cockpit gongwen` |
| `im-triage` | IM 消息分诊 | `cockpit im-triage` |
| `intent` | 🧠 自然语言意图解构与工程规格编译器 (ADR-0195) | `cockpit intent` |
| `omo` | OMO 健康自管系统 | `cockpit omo` |
| `render` | 渲染输出 | `cockpit render` |
| `spine` | Spine 主干真值流与署名自进化操作 (ADR-0437) | `cockpit spine` |

### 🔌 总线接入 (ECCP)

| Subcommand | Summary | Example Usage |
| :--- | :--- | :--- |
| `channels` | External channels inventory (ECCP) | `cockpit channels` |

---

## 5. Observability & Prometheus Telemetry
Cockpit tracks command execution latency, counts, and error rates using an atomic local ring buffer (`~/.workspace/telemetry/cockpit_metrics.json`) with zero external daemon requirements.

```bash
# View telemetry summary table
cockpit telemetry

# Export standard Prometheus exposition text
cockpit telemetry export

# Export structured JSON
cockpit telemetry --json
```

---

## 6. Shell Auto-completion
Cockpit generates native auto-completion scripts for Bash, Zsh, and Fish shells.

### Bash
```bash
source <(cockpit completion bash)
# Persist to ~/.bashrc:
cockpit completion bash > ~/.cockpit-completion.bash
echo 'source ~/.cockpit-completion.bash' >> ~/.bashrc
```

### Zsh
```zsh
# Add to fpath or source directly:
source <(cockpit completion zsh)
```

### Fish
```fish
cockpit completion fish > ~/.config/fish/completions/cockpit.fish
```

