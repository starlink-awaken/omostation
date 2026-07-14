# omostation · eCOS v6

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/starlink-awaken/omostation/actions/workflows/workspace.yml/badge.svg)](https://github.com/starlink-awaken/omostation/actions)

> Multi-project knowledge engineering and AI operating-system workspace.
> Runtime state lives in [`.omo/state/system.yaml`](.omo/state/system.yaml).
> Project metadata lives in [`docs/project-registry.yaml`](docs/project-registry.yaml).

[English](#english) | [中文](#中文)

---

<a name="english"></a>

## English

### What This Is

`omostation` is the root workspace for eCOS v6: a layered system for knowledge engineering, agent governance, BOS service routing, runtime orchestration, and personal/work knowledge operations.

This README is only the front door. It intentionally avoids hard-coded runtime numbers such as phase, health score, test counts, tool counts, service counts, and ports.

### Architecture

For the complete architecture, read [`ARCHITECTURE.md`](ARCHITECTURE.md). Project layer placement is generated from [`docs/project-registry.yaml`](docs/project-registry.yaml) into [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md).

### Entry Points

| Audience | Entry | Source Of Truth |
|----------|-------|-----------------|
| Human CLI/Web | `cockpit` | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| AI agent | `agora` MCP with `bos://` URIs | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Agent workflow | `bin/agent-workflow.py status` / `cockpit agent status` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| Runtime state sync | `uv run --project projects/omo omo state sync` | [`.omo/_truth/registry/mutation-surfaces.yaml`](.omo/_truth/registry/mutation-surfaces.yaml) |
| Governance evolution | `cockpit governance evolution` | [`.omo/_truth/registry/governance-evolution-roadmap.yaml`](.omo/_truth/registry/governance-evolution-roadmap.yaml) |
| Governance | `omo` CLI/MCP broker | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| MOF model governance | `mof-*` tools via agent workflow | [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml) |
| External adapter contracts | `bin/agent-workflow.py adapters` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |

### Quick Start

```bash
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation

bash tests/integration/run-all.sh

cd projects/kairon && make test-diff
cd projects/agora && uv run pytest tests/ -q
cd projects/gbrain && bun test
```

### Documentation Map

| Document | Purpose |
|----------|---------|
| **[`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md)** | **NEW: Unified navigation hub - START HERE** |
| [`docs/INDEX-PROJECTS.md`](docs/INDEX-PROJECTS.md) | Project index by layer/stack |
| [`docs/INDEX-TOOLS.md`](docs/INDEX-TOOLS.md) | Tools and scripts index |
| [`docs/INDEX-KNOWLEDGE.md`](docs/INDEX-KNOWLEDGE.md) | ADRs, audits, patterns index |
| [`docs/INDEX-AGENTS.md`](docs/INDEX-AGENTS.md) | Agent skills and setup index |
| [`AGENTS.md`](AGENTS.md) | Agent/developer operating guide |
| [`CLAUDE.md`](CLAUDE.md) | AI session context loader |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architecture contracts |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Layer and project placement |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | System panorama and BOS routing |
| [`docs/ARCHITECTURE-DETAILED-MAP.md`](docs/ARCHITECTURE-DETAILED-MAP.md) | Architecture deep-dive |
| [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](docs/FUNCTIONAL-CAPABILITY-MAP.md) | Functional capability map |
| [`docs/I0-AGORA-CALLCHAIN.md`](docs/I0-AGORA-CALLCHAIN.md) | Agora BOS URI callchain |
| [`docs/VISION-ROADMAP.md`](docs/VISION-ROADMAP.md) | Vision and roadmap |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | Project metadata SSOT |
| [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | Documentation SSOT contract |

### Governance

- Runtime state: [`.omo/state/system.yaml`](.omo/state/system.yaml)
- Current goals: [`.omo/goals/current.yaml`](.omo/goals/current.yaml)
- Governance kernel: [`projects/omo/`](projects/omo/)
- Governance-as-Code registry: [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml)
- Executable agent workflows and AGCP status: [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml)
- Runtime projection sync: `uv run --project projects/omo omo state sync`
- Governance evolution roadmap: [`.omo/_truth/registry/governance-evolution-roadmap.yaml`](.omo/_truth/registry/governance-evolution-roadmap.yaml)
- MOF capability registry: [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml)

### License

MIT © [starlink-awaken](https://github.com/starlink-awaken)

---

<a name="中文"></a>

## 中文

### 这是什么

`omostation` 是 eCOS v6 的根工作区，用来承载知识工程、Agent 治理、BOS 服务路由、运行时编排，以及个人/工作知识操作。

本 README 只做入口导航，不维护 Phase、健康分、测试数、工具数、服务数、端口等易漂移事实。那些事实有各自的 SSOT。

### 架构速览

完整架构见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。项目分层索引由 [`docs/project-registry.yaml`](docs/project-registry.yaml) 生成到 [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md)。

### 入口

| 受众 | 入口 | 权威来源 |
|------|------|----------|
| 人类 CLI/Web | `cockpit` | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| AI Agent | `agora` MCP + `bos://` URI | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Agent 工作流 | `bin/agent-workflow.py status` / `cockpit agent status` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| 运行态状态同步 | `uv run --project projects/omo omo state sync` | [`.omo/_truth/registry/mutation-surfaces.yaml`](.omo/_truth/registry/mutation-surfaces.yaml) |
| 治理演进 | `cockpit governance evolution` | [`.omo/_truth/registry/governance-evolution-roadmap.yaml`](.omo/_truth/registry/governance-evolution-roadmap.yaml) |
| 治理操作 | `omo` CLI/MCP broker | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| MOF 模型治理 | agent workflow 调用 `mof-*` 工具 | [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml) |
| 外部适配器契约 | `bin/agent-workflow.py adapters` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |

### 快速开始

```bash
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation

bash tests/integration/run-all.sh

cd projects/kairon && make test-diff
cd projects/agora && uv run pytest tests/ -q
cd projects/gbrain && bun test
```

### 文档地图

| 文档 | 用途 |
|------|------|
| **[`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md)** | **全新: 统一导航中心 - 从这里开始** |
| [`docs/INDEX-PROJECTS.md`](docs/INDEX-PROJECTS.md) | 按层/栈的项目索引 |
| [`docs/INDEX-TOOLS.md`](docs/INDEX-TOOLS.md) | 工具和脚本索引 |
| [`docs/INDEX-KNOWLEDGE.md`](docs/INDEX-KNOWLEDGE.md) | ADR、审计、模式索引 |
| [`docs/INDEX-AGENTS.md`](docs/INDEX-AGENTS.md) | Agent 技能和设置索引 |
| [`AGENTS.md`](AGENTS.md) | Agent / 开发者操作指南 |
| [`CLAUDE.md`](CLAUDE.md) | AI 会话上下文加载器 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 稳定架构契约 |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | 分层与项目位置索引 |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | 系统全景与 BOS 路由 |
| [`docs/ARCHITECTURE-DETAILED-MAP.md`](docs/ARCHITECTURE-DETAILED-MAP.md) | 架构细化地图 |
| [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](docs/FUNCTIONAL-CAPABILITY-MAP.md) | 功能能力地图 |
| [`docs/I0-AGORA-CALLCHAIN.md`](docs/I0-AGORA-CALLCHAIN.md) | Agora BOS URI 调用链 |
| [`docs/VISION-ROADMAP.md`](docs/VISION-ROADMAP.md) | 愿景与路线图 |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | 项目元数据 SSOT |
| [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | 文档 SSOT 契约 |

### 治理

- 运行时状态: [`.omo/state/system.yaml`](.omo/state/system.yaml)
- 当前目标: [`.omo/goals/current.yaml`](.omo/goals/current.yaml)
- 治理内核: [`projects/omo/`](projects/omo/)
- Governance-as-Code 注册表: [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml)
- 可执行 Agent 工作流与 AGCP 状态入口: [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml)
- 运行态投影同步: `uv run --project projects/omo omo state sync`
- 治理演进路线图: [`.omo/_truth/registry/governance-evolution-roadmap.yaml`](.omo/_truth/registry/governance-evolution-roadmap.yaml)
- MOF 能力注册表: [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml)

### 许可证

MIT © [starlink-awaken](https://github.com/starlink-awaken)
