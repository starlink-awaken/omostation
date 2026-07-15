# omostation · eCOS v6

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/starlink-awaken/omostation/actions/workflows/workspace.yml/badge.svg)](https://github.com/starlink-awaken/omostation/actions)

> 知识工程与 AI 操作系统工作区 — 多项目、多语言、多层次。

[English](#english) | [中文](#中文)

---

<a name="english"></a>

## English

### Overview

**omostation** is the root workspace of **eCOS v6**, a polyglot monorepo that integrates knowledge engineering, agent governance, BOS service routing, runtime orchestration, and personal/work knowledge operations.

It is organized as a **5+4+1+1 layered architecture**:

| Layer | Name | Projects | Role |
|-------|------|----------|------|
| **L0** | Protocol | `ecos` | SSB signature chain, MOF metamodel, L0 constraints |
| **L1** | Runtime | `runtime` | Matrix/Scheduler/KEI sandbox |
| **L2** | Engine | `kairon`, `gbrain`, `omo`, `metaos`, `omo-debt`, `family-hub` | Knowledge engine, governance kernel, knowledge store |
| **L3** | Entry | `cockpit`, `cockpit-ui` | Unified CLI/Web dashboard |
| **L4** | Self | `l4-kernel` | Self-management domain |
| **I0** | Weave | `agora` | MCP Hub, BOS URI routing mesh |
| **M0** | Crosscut | `model-driven` | Lifecycle meta-framework |
| **X** | Extension | `aetherforge`, `c2g`, `bus-foundation`, `observability` | Compute, strategy, bus, observability |

> Architecture contracts: [`ARCHITECTURE.md`](ARCHITECTURE.md)
> Project layer index: [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md)
> Layer dependency rules: [`docs/layer-contract.yaml`](docs/layer-contract.yaml)

### Entry Points

| Audience | Entry | Source of Truth |
|----------|-------|-----------------|
| Human CLI/Web | `cockpit` | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| AI Agent | `agora` MCP with `bos://` URIs | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Agent workflow | `bin/agent-workflow.py` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| Runtime state | `omo state sync` | [`.omo/state/system.yaml`](.omo/state/system.yaml) |
| Governance | `omo` CLI/MCP | [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml) |

### Quick Start

```bash
# Clone with submodules
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation

# Run the full local gate
make ci-local-fast

# Or run specific checks
make check-layers        #  Layer dependency validation
make ssot-status         #  SSOT file change tracking
make gac-local-gate      #  Full governance-as-code gate

# Run project tests
cd projects/kairon && make test-diff
cd projects/gbrain && bun test
```

### Governance Tools

| Tool | Command | Purpose |
|------|---------|---------|
| Layer dependency check | `make check-layers` | Validates cross-layer imports against [`docs/layer-contract.yaml`](docs/layer-contract.yaml) |
| SSOT watcher | `make ssot-{status,log,sync}` | SHA-256 change tracking for 12 SSOT files, audit log in `.omo/ssot-audit-log.jsonl` |
| GaC local gate | `make gac-local-gate` | Full governance gate (validate, drift, lint, AGCP, MOF, SSOT) |
| Agent workflow | `bin/agent-workflow.py` | Workflow lifecycle: bootstrap, start, claim, verify, closeout, compliance |
| API versioning | `/api/version`, `/api/version/history` | Cockpit API version management with FastAPI middleware |

### Navigation

| Document | Purpose |
|----------|---------|
| [`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md) | **Start here** — unified navigation hub |
| [`docs/INDEX-PROJECTS.md`](docs/INDEX-PROJECTS.md) | Projects by layer and stack |
| [`docs/INDEX-TOOLS.md`](docs/INDEX-TOOLS.md) | Tools and scripts |
| [`docs/INDEX-KNOWLEDGE.md`](docs/INDEX-KNOWLEDGE.md) | ADRs, audits, patterns |
| [`docs/INDEX-AGENTS.md`](docs/INDEX-AGENTS.md) | Agent skills and setup |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architecture contracts |
| [`AGENTS.md`](AGENTS.md) | Agent/developer operating guide |
| [`CLAUDE.md`](CLAUDE.md) | AI session context loader |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | BOS routing and system panorama |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | Project metadata SSOT |

### License

MIT © [starlink-awaken](https://github.com/starlink-awaken)

---

<a name="中文"></a>

## 中文

### 概述

**omostation** 是 **eCOS v6** 的根工作区，一个多语言、多项目的知识工程与 AI 操作系统工作区。

采用 **5+4+1+1 分层架构**：

| 层 | 名称 | 项目 | 职责 |
|----|------|------|------|
| **L0** | 协议层 | `ecos` | SSB 签名链、MOF 元模型、L0 约束 |
| **L1** | 运行时层 | `runtime` | Matrix/Scheduler/KEI 沙箱 |
| **L2** | 引擎层 | `kairon`, `gbrain`, `omo`, `metaos`, `omo-debt`, `family-hub` | 知识引擎、治理中枢、知识库 |
| **L3** | 入口层 | `cockpit`, `cockpit-ui` | 统一 CLI/Web 仪表盘 |
| **L4** | 自我层 | `l4-kernel` | 自我管理面 |
| **I0** | 织层 | `agora` | MCP Hub、BOS URI 路由网 |
| **M0** | 横切框架 | `model-driven` | 生命周期元框架 |
| **X** | 扩展层 | `aetherforge`, `c2g`, `bus-foundation`, `observability` | 算力、战略、总线、可观测性 |

> 架构契约: [`ARCHITECTURE.md`](ARCHITECTURE.md)
> 项目分层索引: [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md)
> 分层依赖规则: [`docs/layer-contract.yaml`](docs/layer-contract.yaml)

### 入口

| 受众 | 入口 | 权威来源 |
|------|------|----------|
| 人类 CLI/Web | `cockpit` | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| AI Agent | `agora` MCP + `bos://` URI | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Agent 工作流 | `bin/agent-workflow.py` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| 运行态状态 | `omo state sync` | [`.omo/state/system.yaml`](.omo/state/system.yaml) |
| 治理操作 | `omo` CLI/MCP | [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml) |

### 快速开始

```bash
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation

# 本地全部门
make ci-local-fast

# 或运行特定检查
make check-layers        #  分层依赖验证
make ssot-status         #  SSOT 变更追踪
make gac-local-gate      #  全量治理-as-Code 门禁

# 项目测试
cd projects/kairon && make test-diff
cd projects/gbrain && bun test
```

### 治理工具

| 工具 | 命令 | 用途 |
|------|------|------|
| 分层依赖检查 | `make check-layers` | 验证跨层导入是否符合 [`docs/layer-contract.yaml`](docs/layer-contract.yaml) |
| SSOT 追踪 | `make ssot-{status,log,sync}` | 12 个 SSOT 文件的 SHA-256 变更追踪，审计日志在 `.omo/ssot-audit-log.jsonl` |
| GaC 本地门禁 | `make gac-local-gate` | 全量治理门禁 (validate, drift, lint, AGCP, MOF, SSOT) |
| Agent 工作流 | `bin/agent-workflow.py` | 工作流生命周期: bootstrap, start, claim, verify, closeout, compliance |
| API 版本管理 | `/api/version`, `/api/version/history` | Cockpit API 版本管理，FastAPI 中间件 |

### 文档导航

| 文档 | 用途 |
|------|------|
| [`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md) | **从这里开始** — 统一导航中心 |
| [`docs/INDEX-PROJECTS.md`](docs/INDEX-PROJECTS.md) | 按层/栈的项目索引 |
| [`docs/INDEX-TOOLS.md`](docs/INDEX-TOOLS.md) | 工具和脚本索引 |
| [`docs/INDEX-KNOWLEDGE.md`](docs/INDEX-KNOWLEDGE.md) | ADR、审计、模式索引 |
| [`docs/INDEX-AGENTS.md`](docs/INDEX-AGENTS.md) | Agent 技能和设置索引 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 稳定架构契约 |
| [`AGENTS.md`](AGENTS.md) | Agent / 开发者操作指南 |
| [`CLAUDE.md`](CLAUDE.md) | AI 会话上下文加载器 |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | BOS 路由与系统全景 |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | 项目元数据 SSOT |

### 许可证

MIT © [starlink-awaken](https://github.com/starlink-awaken)
